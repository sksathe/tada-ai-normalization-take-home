"""Explicit mappings. Unlisted leaves are retained, never silently treated as normalized."""


def rules(text):
    result = {}
    for line in text.strip().splitlines():
        source, target, *kind = line.split()
        result[source] = (target, kind[0] if kind else "copy")
    return result


MAPPINGS = {
 "prismhr": {
 "company": rules('''id source_id
clientName name
legalName legal_name
federalIdNumber tax_id
emailAddress email
mainPhone phone
addressLine1 address.line1
addressLine2 address.line2
city address.city
stateCode address.state
zipCode address.postal_code
websiteUrl website'''),
 "employee": rules('''id source_id
firstName first_name
lastName last_name
middleInitial middle_name
preferredName preferred_name
person.birthDate birth_date date
person.maritalStatus marital_status_raw
person.gender gender_raw
person.preferredLanguage preferred_language
person.emergencyContact emergency_contacts
person.employerIds employer_ids
contactInformation.addressLine1 address.line1
contactInformation.addressLine2 address.line2
contactInformation.city address.city
contactInformation.state address.state
contactInformation.zipcode address.postal_code
contactInformation.homePhone home_phone
contactInformation.mobilePhone mobile_phone
contactInformation.emailAddress personal_email
client.workEmail work_email
client.workPhone work_phone
client.clientEmployeeId employee_number
client.employeeStatus employment_status_raw
client.statusClass employment_status prism_status
client.statusDate status_effective_date date
client.employeeType employment_type_raw
client.firstHireDate original_hire_date date
client.lastHireDate hire_date date
client.jobCode job_code
client.jobStartDate job_start_date date
client.homeDepartment department_code
client.homeDivision division_code
client.homeLocation location_code
client.manager manager_source_id
client.reportsTo approver_source_id
client.flsaExempt flsa_exempt
client.unionCode union_code
client.workGroupCode work_group_code
compensation.payMethod compensation.pay_basis prism_pay
compensation.hourlyPay compensation.hourly_rate decimal
compensation.salary compensation.period_salary decimal
compensation.annualPay compensation.annual_salary decimal
compensation.standardHours compensation.standard_hours decimal
compensation.payGroup compensation.pay_group
compensation.payPeriod compensation.pay_period_raw
compensation.effectiveDate compensation.effective_date date'''),
 "direct_deposit": rules('''accountNum account_number
transitNum routing_number
bankName bank_name
accountType account_type prism_account
method allocation_method prism_method
amount allocation_value decimal
limit allocation_limit decimal
status status prism_deposit_status
voucherTypeOverride voucher_types_raw'''),
 "deduction": rules('''deductionCode code
deductionType type_raw
deductionMethod calculation_method_raw
description description
usePercent is_percentage
amount value decimal
period frequency_raw
startDate start_date date
stopDate end_date date
limit period_limit decimal
maximum maximum decimal
basis maximum_basis_raw
trackArrears tracks_arrears
matchAmount employer_match_value decimal
matchMethod employer_match_method_raw
benefitPlanId benefit_plan_source_id'''),
 "payroll_run": rules('''batchId source_id
description name
type type_raw
payDate pay_date date
grossEarnings gross_pay decimal
employeesPaid employee_count integer
checkCount check_count integer'''),
 "paycheck": rules('''voucherId source_id
employeeId employee_source_id
batchId payroll_run_source_id
checkNumber check_number
payDate pay_date date
payPeriodStart period_start date
payPeriodEnd period_end date
totalEarnings gross_pay decimal
netPay net_pay decimal
type type_raw
status status_raw
voidDate void_date date
earnAmount timesheet_earnings decimal
otherEarnAmount other_earnings_total decimal'''),
 "compensation": rules('''payMethod pay_basis prism_pay
hourlyPay hourly_rate decimal
salary period_salary decimal
annualPay annual_salary decimal
effectiveDate effective_date date
standardHours standard_hours decimal
payGroup pay_group
payPeriod pay_period_raw'''),
 },
 "isolved": {
 "company": rules('''id source_id
legalName legal_name
dbaName name
legalCode company_code
federalEIN tax_id
legalAddress address
status status_raw
naicsCode industry_code'''),
 "employee": rules('''id source_id
employeeNumber employee_number
nameAddress.firstName first_name
nameAddress.lastName last_name
nameAddress.middleName middle_name
nameAddress.preferredName preferred_name
nameAddress.preferredPronouns preferred_pronouns
nameAddress.address1 address.line1
nameAddress.address2 address.line2
nameAddress.city address.city
nameAddress.state address.state
nameAddress.zipCode address.postal_code
emailAddress personal_email
birthDate birth_date date
hireDate hire_date date
originalHireDate original_hire_date date
rehireDate rehire_date date
terminationDate termination_date date
terminationReason termination_reason_raw
employmentStatus employment_status tenant_status
statusDate status_effective_date date
employmentCategoryCode employment_type_raw
employmentCategoryFullTimeEquivalent full_time_equivalent decimal
jobCode job_code
jobTitle job_title
jobEffectiveDate job_start_date date
jobFLSAExempt flsa_exempt
jobIsUnion union_member
organizations organizations
labors labor_assignments
assignedManager manager
assignedSupervisor supervisor
isRemoteWorker remote_worker
hourlyRate compensation.hourly_rate decimal
annualSalary compensation.annual_salary decimal
perPaySalary compensation.period_salary decimal
normalHours compensation.standard_hours decimal
payType compensation.pay_basis_raw
payGroup compensation.pay_group
payFrequency compensation.periods_per_year integer
salaryEffectiveDate compensation.effective_date date
payRates compensation.alternate_rates
gender gender_raw
maritalStatus marital_status_raw
personal personal_details
taxes tax_configuration
miscFields custom_fields'''),
 "direct_deposit": rules('''id source_id
accountNumber account_number
routingNumber routing_number
accountType account_type_raw
bankName bank_name
amount amount decimal
percent percentage decimal
sequenceNumber priority integer
status status_raw
frequency frequency_raw'''),
 "deduction": rules('''id source_id
employeeId employee_source_id
payItemCode code
payItemName description
payItemType type_raw
calcParams calculation_parameters
scheduleOverride frequency_raw
startDate start_date date
stopDate end_date date'''),
 "payroll_run": rules('''id source_id
runNumber run_number integer
payDate pay_date date
periodBeginDate period_start date
periodEndDate period_end date
status status_raw
payrollRunType type_raw
runDate run_date date
submittedDate submitted_date date'''),
 "paycheck": rules('''id source_id
employeeId employee_source_id
payrollRunNumber payroll_run_number integer
checkNumber check_number
checkDate pay_date date
periodBeginDate period_start date
periodEndDate period_end date
grossPay gross_pay decimal
netPay net_pay decimal
checkAmount check_amount decimal
directDepositAmount direct_deposit_amount decimal
checkTypeDescription type_raw'''),
 },
 "ukg-ready": {
 "demographics": rules('''citizenship citizenship_raw
ethnicity ethnicity_raw
gender gender_raw
full_time_student full_time_student
seasonal seasonal
visa visa
recruiter recruiter
referral referral
eye_color eye_color
height height_raw'''),
 "pay_info": rules('''default_job.id job_source_id
job_change_reason_code.display_name job_change_reason
job_last_changed job_start_date date
standard_work_day standard_work_day_milliseconds integer
employee_type.id employment_type_source_id
pay_type.id pay_type_source_id
shift_premium.id shift_premium_source_id
medical_eligibility medical_eligibility_raw
dental_eligibility dental_eligibility_raw
dependent_benefits_eligibility dependent_benefits_eligibility_raw
benefit_auto_enrollment_eligibility benefit_auto_enrollment_eligibility_raw
eeo_classification eeo_classification_raw
eeo4_classification eeo4_classification_raw
eeo4_function eeo4_function_raw
workers_comp_code.external_id workers_comp_code
union.id union_source_id
payroll_classification payroll_classification_raw
pay_grade pay_grade
gl_codes general_ledger_codes
ttoc ttoc'''),
 "custom_fields": rules('''hr_custom_fields custom_fields'''),
 "employee": rules('''id source_id
employee_id employee_number
external_id external_id
username username
first_name first_name
last_name last_name
middle_name middle_name
nickname preferred_name
status employment_status tenant_status
primary_email personal_email
secondary_email secondary_email
phones phones
address.address_line_1 address.line1
address.address_line_2 address.line2
address.address_line_3 address.line3
address.city address.city
address.state_code address.state
address.zip address.postal_code
address.country address.country
mailing_address mailing_address
dates.hired hire_date date
dates.re_hired rehire_date date
dates.birthday birth_date date
dates.terminated termination_date date
dates.seniority seniority_date date
managers managers
ein.id legal_entity_source_id
cost_centers_info organization_assignments
account_extra_fields custom_fields
national_id_numbers national_identifiers'''),
 "direct_deposit": rules('''id source_id
account_number account_number
routing_number routing_number
account_type account_type ukg_account
sequence priority integer
calc_method.type allocation_method ukg_method
amount amount decimal
percentage percentage decimal
active active
active_from start_date date
active_to end_date date
pre_note_status prenote_status_raw
currency currency
type type_raw
payroll_frequency frequency'''),
 "deduction": rules('''id source_id
deduction.code code
deduction.name description
sequence priority integer
effective_from start_date date
effective_to end_date date
ee_calc_method.amount amount decimal
ee_calc_method.percent percentage decimal
ee_calc_method.method.type calculation_method_raw
annual_max_amount annual_limit decimal
er_annual_max_amount employer_annual_limit decimal
ee_frequency employee_frequency
er_frequency employer_frequency
vendor vendor
cost_centers organization_assignments'''),
 "payroll_run": rules('''id source_id
name name
start_date period_start date
end_date period_end date
pay_date pay_date date
date_finalized finalized_date date
status status_raw
type type_raw
ein.id legal_entity_source_id'''),
 "paycheck": rules('''id source_id
employee.account_id employee_source_id
pay_date pay_date date
pay_period_start period_start date
pay_period_end period_end date
status status_raw
type type_raw'''),
 "compensation": rules('''id source_id
employee.account_id employee_source_id
effective_from effective_date date
amount amount decimal
hourly_pay hourly_rate decimal
currency currency
amount_period amount_period_raw
time duration_milliseconds integer
time_period duration_period_raw
num_pp_in_year periods_per_year integer
auto_pay auto_pay'''),
 },
}

ENUMS = {
 "prism_status": {"A": "active", "L": "on_leave", "T": "terminated"},
 "prism_pay": {"H": "hourly", "S": "salary", "C": "commission", "D": "driver"},
 "prism_account": {"C": "checking_or_pay_card", "S": "savings", "IP": "instant_pay"},
 "prism_method": {"F": "fixed", "P": "percentage", "FS": "fixed_skip_underfunded",
                  "PN": "percentage_after_fixed", "B": "remaining_balance"},
 "prism_deposit_status": {"P": "prenote", "D": "active", "I": "inactive"},
 "ukg_account": {"CHECKING": "checking", "SAVINGS": "savings"},
 "ukg_method": {"FULL": "remaining_balance", "FLAT_AMOUNT": "fixed", "GROSS_EARNING": "percentage_of_gross",
                "NET_PAY": "percentage_of_net", "DIRECT_DEPOSIT_PER_OF_REMAINDER": "percentage_of_remainder"},
}
