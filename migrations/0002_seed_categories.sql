-- Seed Plaid personal finance category taxonomy.
-- IDs are lowercase snake_case of the Plaid category key.
-- Primary categories have parent_id = NULL.
-- Detailed sub-categories reference their primary via parent_id.
BEGIN TRANSACTION;

-- ── Primary categories ────────────────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('income',                  'Income',                   NULL, 1),
  ('transfer_in',             'Transfer In',              NULL, 1),
  ('transfer_out',            'Transfer Out',             NULL, 1),
  ('loan_payments',           'Loan Payments',            NULL, 1),
  ('bank_fees',               'Bank Fees',                NULL, 1),
  ('entertainment',           'Entertainment',            NULL, 1),
  ('food_and_drink',          'Food and Drink',           NULL, 1),
  ('general_merchandise',     'General Merchandise',      NULL, 1),
  ('home_improvement',        'Home Improvement',         NULL, 1),
  ('medical',                 'Medical',                  NULL, 1),
  ('personal_care',           'Personal Care',            NULL, 1),
  ('general_services',        'General Services',         NULL, 1),
  ('government_and_non_profit','Government and Non-Profit',NULL, 1),
  ('transportation',          'Transportation',           NULL, 1),
  ('travel',                  'Travel',                   NULL, 1),
  ('rent_and_utilities',      'Rent and Utilities',       NULL, 1);

-- ── INCOME sub-categories ─────────────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('income_dividends',            'Dividends',                'income', 1),
  ('income_foreign_cash_deposits','Foreign Cash Deposits',    'income', 1),
  ('income_interest_earned',      'Interest Earned',          'income', 1),
  ('income_retirement_pension',   'Retirement / Pension',     'income', 1),
  ('income_tax_refund',           'Tax Refund',               'income', 1),
  ('income_unemployment',         'Unemployment',             'income', 1),
  ('income_wages',                'Wages',                    'income', 1),
  ('income_other_income',         'Other Income',             'income', 1);

-- ── TRANSFER_IN sub-categories ────────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('transfer_in_cash_advances_and_loans',       'Cash Advances and Loans',          'transfer_in', 1),
  ('transfer_in_deposit',                        'Deposit',                          'transfer_in', 1),
  ('transfer_in_investment_and_retirement_funds','Investment and Retirement Funds',  'transfer_in', 1),
  ('transfer_in_savings',                        'Savings',                          'transfer_in', 1),
  ('transfer_in_account_transfer',               'Account Transfer',                 'transfer_in', 1),
  ('transfer_in_other_transfer_in',              'Other Transfer In',                'transfer_in', 1);

-- ── TRANSFER_OUT sub-categories ───────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('transfer_out_investment_and_retirement_funds','Investment and Retirement Funds', 'transfer_out', 1),
  ('transfer_out_savings',                        'Savings',                         'transfer_out', 1),
  ('transfer_out_withdrawal',                     'Withdrawal',                      'transfer_out', 1),
  ('transfer_out_account_transfer',               'Account Transfer',                'transfer_out', 1),
  ('transfer_out_other_transfer_out',             'Other Transfer Out',              'transfer_out', 1);

-- ── LOAN_PAYMENTS sub-categories ─────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('loan_payments_car_payment',            'Car Payment',             'loan_payments', 1),
  ('loan_payments_credit_card_payment',    'Credit Card Payment',     'loan_payments', 1),
  ('loan_payments_personal_loan_payment',  'Personal Loan Payment',   'loan_payments', 1),
  ('loan_payments_realtor_payment',        'Realtor Payment',         'loan_payments', 1),
  ('loan_payments_student_loan_payment',   'Student Loan Payment',    'loan_payments', 1),
  ('loan_payments_other_payment',          'Other Payment',           'loan_payments', 1);

-- ── BANK_FEES sub-categories ──────────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('bank_fees_atm_fees',                 'ATM Fees',                   'bank_fees', 1),
  ('bank_fees_foreign_transaction_fees', 'Foreign Transaction Fees',   'bank_fees', 1),
  ('bank_fees_insufficient_funds',       'Insufficient Funds',         'bank_fees', 1),
  ('bank_fees_interest_charge',          'Interest Charge',            'bank_fees', 1),
  ('bank_fees_overdraft_fees',           'Overdraft Fees',             'bank_fees', 1),
  ('bank_fees_other_bank_fees',          'Other Bank Fees',            'bank_fees', 1);

-- ── ENTERTAINMENT sub-categories ─────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('entertainment_casinos_and_gambling',                          'Casinos and Gambling',                              'entertainment', 1),
  ('entertainment_music_and_audio',                               'Music and Audio',                                   'entertainment', 1),
  ('entertainment_sporting_events_amusement_parks_and_museums',   'Sporting Events, Amusement Parks, and Museums',     'entertainment', 1),
  ('entertainment_tv_and_movies',                                 'TV and Movies',                                     'entertainment', 1),
  ('entertainment_video_games',                                   'Video Games',                                       'entertainment', 1),
  ('entertainment_other_entertainment',                           'Other Entertainment',                               'entertainment', 1);

-- ── FOOD_AND_DRINK sub-categories ─────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('food_and_drink_beer_wine_and_liquor',   'Beer, Wine, and Liquor',   'food_and_drink', 1),
  ('food_and_drink_coffee',                 'Coffee',                   'food_and_drink', 1),
  ('food_and_drink_fast_food',              'Fast Food',                'food_and_drink', 1),
  ('food_and_drink_groceries',              'Groceries',                'food_and_drink', 1),
  ('food_and_drink_restaurant',             'Restaurant',               'food_and_drink', 1),
  ('food_and_drink_vending_machines',       'Vending Machines',         'food_and_drink', 1),
  ('food_and_drink_other_food_and_drink',   'Other Food and Drink',     'food_and_drink', 1);

-- ── GENERAL_MERCHANDISE sub-categories ───────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('general_merchandise_bookstores_and_newsstands', 'Bookstores and Newsstands',  'general_merchandise', 1),
  ('general_merchandise_clothing_and_accessories',  'Clothing and Accessories',   'general_merchandise', 1),
  ('general_merchandise_convenience_stores',        'Convenience Stores',         'general_merchandise', 1),
  ('general_merchandise_department_stores',         'Department Stores',          'general_merchandise', 1),
  ('general_merchandise_discount_stores',           'Discount Stores',            'general_merchandise', 1),
  ('general_merchandise_electronics',               'Electronics',                'general_merchandise', 1),
  ('general_merchandise_gifts_and_novelties',       'Gifts and Novelties',        'general_merchandise', 1),
  ('general_merchandise_office_supplies',           'Office Supplies',            'general_merchandise', 1),
  ('general_merchandise_online_marketplaces',       'Online Marketplaces',        'general_merchandise', 1),
  ('general_merchandise_pet_supplies',              'Pet Supplies',               'general_merchandise', 1),
  ('general_merchandise_sporting_goods',            'Sporting Goods',             'general_merchandise', 1),
  ('general_merchandise_superstores',               'Superstores',                'general_merchandise', 1),
  ('general_merchandise_tobacco_and_vaping',        'Tobacco and Vaping',         'general_merchandise', 1),
  ('general_merchandise_other_general_merchandise', 'Other General Merchandise',  'general_merchandise', 1);

-- ── HOME_IMPROVEMENT sub-categories ──────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('home_improvement_furniture',               'Furniture',               'home_improvement', 1),
  ('home_improvement_hardware',                'Hardware',                'home_improvement', 1),
  ('home_improvement_repair_and_maintenance',  'Repair and Maintenance',  'home_improvement', 1),
  ('home_improvement_security',                'Security',                'home_improvement', 1),
  ('home_improvement_other_home_improvement',  'Other Home Improvement',  'home_improvement', 1);

-- ── MEDICAL sub-categories ────────────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('medical_dental_care',                  'Dental Care',                 'medical', 1),
  ('medical_eye_care',                     'Eye Care',                    'medical', 1),
  ('medical_nursing_care',                 'Nursing Care',                'medical', 1),
  ('medical_pharmacies_and_supplements',   'Pharmacies and Supplements',  'medical', 1),
  ('medical_primary_care',                 'Primary Care',                'medical', 1),
  ('medical_veterinary_services',          'Veterinary Services',         'medical', 1),
  ('medical_other_medical',                'Other Medical',               'medical', 1);

-- ── PERSONAL_CARE sub-categories ─────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('personal_care_gyms_and_fitness_centers',   'Gyms and Fitness Centers',    'personal_care', 1),
  ('personal_care_hair_and_beauty',            'Hair and Beauty',             'personal_care', 1),
  ('personal_care_laundry_and_dry_cleaning',   'Laundry and Dry Cleaning',    'personal_care', 1),
  ('personal_care_other_personal_care',        'Other Personal Care',         'personal_care', 1);

-- ── GENERAL_SERVICES sub-categories ──────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('general_services_accounting_and_financial_planning', 'Accounting and Financial Planning', 'general_services', 1),
  ('general_services_automotive',                        'Automotive',                        'general_services', 1),
  ('general_services_childcare',                         'Childcare',                         'general_services', 1),
  ('general_services_consulting_and_legal',              'Consulting and Legal',              'general_services', 1),
  ('general_services_education',                         'Education',                         'general_services', 1),
  ('general_services_insurance',                         'Insurance',                         'general_services', 1),
  ('general_services_postage_and_shipping',              'Postage and Shipping',              'general_services', 1),
  ('general_services_storage',                           'Storage',                           'general_services', 1),
  ('general_services_other_general_services',            'Other General Services',            'general_services', 1);

-- ── GOVERNMENT_AND_NON_PROFIT sub-categories ──────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('government_and_non_profit_donations',                          'Donations',                              'government_and_non_profit', 1),
  ('government_and_non_profit_government_departments_and_agencies','Government Departments and Agencies',    'government_and_non_profit', 1),
  ('government_and_non_profit_tax_payment',                        'Tax Payment',                           'government_and_non_profit', 1),
  ('government_and_non_profit_other_government_and_non_profit',    'Other Government and Non-Profit',       'government_and_non_profit', 1);

-- ── TRANSPORTATION sub-categories ─────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('transportation_bikes_and_scooters',       'Bikes and Scooters',     'transportation', 1),
  ('transportation_gas',                      'Gas',                    'transportation', 1),
  ('transportation_parking',                  'Parking',                'transportation', 1),
  ('transportation_public_transit',           'Public Transit',         'transportation', 1),
  ('transportation_taxis_and_ride_shares',    'Taxis and Ride Shares',  'transportation', 1),
  ('transportation_tolls',                    'Tolls',                  'transportation', 1),
  ('transportation_other_transportation',     'Other Transportation',   'transportation', 1);

-- ── TRAVEL sub-categories ─────────────────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('travel_flights',        'Flights',        'travel', 1),
  ('travel_lodging',        'Lodging',        'travel', 1),
  ('travel_rental_cars',    'Rental Cars',    'travel', 1),
  ('travel_other_travel',   'Other Travel',   'travel', 1);

-- ── RENT_AND_UTILITIES sub-categories ─────────────────────────────────────────

INSERT INTO category (id, name, parent_id, active) VALUES
  ('rent_and_utilities_gas_and_utilities',          'Gas and Utilities',          'rent_and_utilities', 1),
  ('rent_and_utilities_internet_and_cable',         'Internet and Cable',         'rent_and_utilities', 1),
  ('rent_and_utilities_rent',                       'Rent',                       'rent_and_utilities', 1),
  ('rent_and_utilities_sewage_and_waste_management','Sewage and Waste Management','rent_and_utilities', 1),
  ('rent_and_utilities_telephone',                  'Telephone',                  'rent_and_utilities', 1),
  ('rent_and_utilities_water',                      'Water',                      'rent_and_utilities', 1),
  ('rent_and_utilities_other_utilities',            'Other Utilities',            'rent_and_utilities', 1);

INSERT INTO schema_version (
  version, applied_at_utc, applied_at_tz, applied_at_offset_minutes
) VALUES (2, '2026-02-22T00:00:00', 'UTC', 0);

COMMIT;
