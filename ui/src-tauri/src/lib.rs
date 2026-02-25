/// Godzilla Tauri application runtime.
///
/// REQ: SEC-ACC-004, SEC-DATA-001, SEC-NET-001, SEC-NET-002

use std::collections::HashMap;
use std::fs;

use base64::Engine as _;
use base64::engine::general_purpose::STANDARD as BASE64_STANDARD;
use reqwest::Method;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct ApiProxyHeader {
    name: String,
    value: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ApiProxyRequest {
    method: String,
    path: String,
    headers: Vec<ApiProxyHeader>,
    body_base64: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ApiProxyResponse {
    status: u16,
    headers: Vec<ApiProxyHeader>,
    body_base64: String,
}

fn normalize_fingerprint(value: &str) -> String {
    value
        .chars()
        .filter(|ch| ch.is_ascii_hexdigit())
        .collect::<String>()
        .to_uppercase()
}

fn pem_to_der_bytes(pem_text: &str) -> Result<Vec<u8>, String> {
    let body = pem_text
        .lines()
        .filter(|line| !line.starts_with("-----BEGIN") && !line.starts_with("-----END"))
        .map(str::trim)
        .collect::<String>();
    BASE64_STANDARD
        .decode(body.as_bytes())
        .map_err(|err| format!("Failed to decode PEM certificate: {err}"))
}

fn sha256_hex_upper(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|b| format!("{b:02X}")).collect::<String>()
}

fn verify_pinned_certificate() -> Result<Vec<u8>, String> {
    // REQ: SEC-NET-001 — enforce explicit certificate pinning in Tauri runtime transport.
    let cert_path = std::env::var("GODZILLA_TLS_CERT")
        .map_err(|_| "GODZILLA_TLS_CERT is not configured".to_string())?;
    let expected = std::env::var("GODZILLA_TLS_CERT_SHA256")
        .map_err(|_| "GODZILLA_TLS_CERT_SHA256 is not configured".to_string())?;
    let cert_pem = fs::read(&cert_path)
        .map_err(|err| format!("Unable to read TLS cert at '{cert_path}': {err}"))?;
    let cert_pem_text = String::from_utf8(cert_pem.clone())
        .map_err(|err| format!("TLS cert is not valid UTF-8 PEM: {err}"))?;
    let cert_der = pem_to_der_bytes(&cert_pem_text)?;
    let actual = sha256_hex_upper(&cert_der);
    if normalize_fingerprint(&expected) != actual {
        return Err("TLS certificate pin mismatch".to_string());
    }
    Ok(cert_pem)
}

/// Proxy an API request through the Tauri backend so runtime HTTPS can use
/// explicit local certificate trust + pin verification.
///
/// REQ: SEC-NET-001, SEC-NET-002
#[tauri::command]
fn api_request(request: ApiProxyRequest) -> Result<ApiProxyResponse, String> {
    let cert_pem = verify_pinned_certificate()?;
    let certificate = reqwest::Certificate::from_pem(&cert_pem)
        .map_err(|err| format!("Failed to parse TLS certificate: {err}"))?;

    let method = Method::from_bytes(request.method.as_bytes())
        .map_err(|err| format!("Invalid HTTP method '{}': {err}", request.method))?;

    if request.path.starts_with("http://") || request.path.starts_with("https://") {
        return Err("Path must be relative (e.g. /accounts)".to_string());
    }
    let normalized_path = if request.path.starts_with('/') {
        request.path
    } else {
        format!("/{}", request.path)
    };
    let base_url = std::env::var("GODZILLA_API_BASE").unwrap_or_else(|_| "https://127.0.0.1:8787".to_string());
    let endpoint = format!("{}{}", base_url.trim_end_matches('/'), normalized_path);

    let mut header_map = HashMap::<String, String>::new();
    for header in request.headers {
        header_map.insert(header.name, header.value);
    }

    let body = request
        .body_base64
        .map(|value| {
            BASE64_STANDARD
                .decode(value.as_bytes())
                .map_err(|err| format!("Invalid request body encoding: {err}"))
        })
        .transpose()?;

    let client = reqwest::blocking::Client::builder()
        .add_root_certificate(certificate)
        .https_only(true)
        .build()
        .map_err(|err| format!("Failed to initialize HTTPS client: {err}"))?;

    let mut req_builder = client.request(method, endpoint);
    for (name, value) in header_map {
        req_builder = req_builder.header(name, value);
    }
    if let Some(bytes) = body {
        req_builder = req_builder.body(bytes);
    }

    let response = req_builder
        .send()
        .map_err(|err| format!("API proxy request failed: {err}"))?;

    let status = response.status().as_u16();
    let headers = response
        .headers()
        .iter()
        .filter_map(|(name, value)| {
            value.to_str().ok().map(|val| ApiProxyHeader {
                name: name.as_str().to_string(),
                value: val.to_string(),
            })
        })
        .collect::<Vec<_>>();
    let body_bytes = response
        .bytes()
        .map_err(|err| format!("Failed to read API response body: {err}"))?;

    Ok(ApiProxyResponse {
        status,
        headers,
        body_base64: BASE64_STANDARD.encode(body_bytes),
    })
}

/// Return the sidecar API token from the process environment so the
/// React frontend can authenticate requests without embedding it in
/// any build artifact or client-side bundle.
///
/// REQ: SEC-ACC-004, SEC-DATA-001
#[tauri::command]
fn get_api_token() -> String {
    std::env::var("GODZILLA_API_TOKEN").unwrap_or_default()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![get_api_token, api_request])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::{normalize_fingerprint, pem_to_der_bytes, sha256_hex_upper};

    #[test]
    fn normalize_fingerprint_strips_non_hex_chars() {
        assert_eq!(
            normalize_fingerprint("aa:bb:cc dd\nee"),
            "AABBCCDDEE"
        );
    }

    #[test]
    fn pem_to_der_bytes_decodes_pem_body() {
        let pem = "-----BEGIN CERTIFICATE-----\nAQIDBA==\n-----END CERTIFICATE-----\n";
        assert_eq!(pem_to_der_bytes(pem).expect("should decode"), vec![1, 2, 3, 4]);
    }

    #[test]
    fn sha256_hex_upper_produces_uppercase_hex() {
        assert_eq!(
            sha256_hex_upper(&[1, 2, 3, 4]),
            "9F64A747E1B97F131FABB6B447296C9B6F0201E79FB3C5356E6C77E89B6A806A"
        );
    }
}
