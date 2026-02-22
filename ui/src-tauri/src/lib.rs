/// Godzilla Tauri application runtime.
///
/// REQ: SEC-ACC-004, SEC-DATA-001

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
        .invoke_handler(tauri::generate_handler![get_api_token])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
