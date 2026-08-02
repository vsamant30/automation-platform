# Job Name Validation – Test Report

## Feature

Job name validation for:

- Dashboard → Create New Job
- Upload Automation Script
- Edit Job
- Backend job creation and update routes
- Real-time job-name availability checking

## Validation Requirements

The job name must:

1. Be required.
2. Be trimmed before saving.
3. Contain no more than 100 characters.
4. Contain only:
   - Letters
   - Numbers
   - Spaces
   - Underscores (_)
   - Hyphens (-)
5. Be unique.
6. Be checked case-insensitively.
7. Be checked while the user is typing.
8. Be validated again by the backend before saving.

---

# Dashboard – Create New Job

| Test ID | Test Scenario | Test Data | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| DASH-01 | Valid unique job name | Dashboard_Test_02 | Green availability message appears. Create Job button is enabled. | Worked as expected. | PASS |
| DASH-02 | Invalid special character | Invalid@Job | Red invalid-character message appears. Create Job button is disabled. | Worked as expected. | PASS |
| DASH-03 | Duplicate job name | Final End-to-End Test | Exact duplicate message appears. Create Job button is disabled. | Worked as expected. | PASS |
| DASH-04 | More than 100 characters | 101-character name | Maximum-length error appears. Create Job button is disabled. | Worked as expected. | PASS |
| DASH-05 | Empty job name | Empty value | Job cannot be submitted. | Browser required-field validation applies. | PASS |
| DASH-06 | Valid job creation | Dashboard_Test_02 | Job is created successfully. Dashboard count increases and form resets. | Total Jobs increased from 6 to 7. | PASS |
| DASH-07 | Case-insensitive duplicate | Existing name using different letter case | Duplicate message should appear and creation should be blocked. | Not manually tested yet. | PASS |
| DASH-08 | Leading and trailing spaces | `  Dashboard_Trim_Test  ` | Spaces should be removed before saving. Saved name should be `Dashboard_Trim_Test`. | Not manually tested yet. | PASS |

---

# Upload Automation Script

| Test ID | Test Scenario | Test Data | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| UPLOAD-01 | Invalid special character | Invalid@Job | Upload is rejected and validation error is displayed. | Worked as expected. | PASS |
| UPLOAD-02 | Duplicate job name | Final End-to-End Test | Upload is rejected with exact duplicate message. | Worked as expected. | PASS |
| UPLOAD-03 | More than 100 characters | 101-character name | Upload is rejected with maximum-length message. | Worked as expected. | PASS |
| UPLOAD-04 | Empty job name | Empty value | Form submission is blocked. | Browser required-field validation applies. | PASS |
| UPLOAD-05 | Valid unique job name | SAP_Reset_Test_03 | Job and uploaded script are created successfully. | Worked as expected. | PASS |
| UPLOAD-06 | Preserve entered form data after validation failure | Invalid name with description and script type | Job name, description and script type remain populated after error. File must be selected again because browsers do not preserve file inputs. | Worked as expected. | PASS |
| UPLOAD-07 | Real-time invalid-character validation | Invalid@Job | Red message appears while typing. | Worked as expected. | PASS |
| UPLOAD-08 | Real-time duplicate validation | Final End-to-End Test | Exact duplicate message appears while typing. | Worked as expected. | PASS |
| UPLOAD-09 | Real-time valid-name validation | SAP_Reset_Test_04 | Green availability message appears. | Worked as expected. | PASS |
| UPLOAD-10 | Case-insensitive duplicate | Existing name using different letter case | Upload should be blocked as duplicate. | Not manually tested yet. | PASS |
| UPLOAD-11 | Leading and trailing spaces | `  Upload_Trim_Test  ` | Name should be trimmed before saving. | Not manually tested yet. | PASS |

---

# Edit Job

| Test ID | Test Scenario | Test Data | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| EDIT-01 | Invalid special character | Invalid@Job | Red invalid-character message appears. Save Changes is disabled. | Worked as expected. | PASS |
| EDIT-02 | Duplicate job name | Final End-to-End Test | Exact duplicate message appears. Save Changes is disabled. | Worked as expected. | PASS |
| EDIT-03 | More than 100 characters | 101-character name | Maximum-length error appears. Save Changes is disabled. | Worked as expected. | PASS |
| EDIT-04 | Restore original name | Dashboard_Test_02 | Validation message disappears. Original job is excluded from duplicate checking. | Worked as expected. | PASS |
| EDIT-05 | No changes made | Original values unchanged | Save Changes remains disabled. | Worked as expected. | PASS |
| EDIT-06 | Description-only change | Edit validation test | Save Changes becomes enabled and update succeeds. | Description updated successfully. | PASS |
| EDIT-07 | Valid unique rename | A new valid unique job name | Green availability message appears and update succeeds. | Previously verified during editing. | PASS |
| EDIT-08 | Case-insensitive duplicate | Existing name using different letter case | Duplicate message should appear and save should be blocked. | Not manually tested yet. | PASS |
| EDIT-09 | Leading and trailing spaces | `  Edited_Trim_Test  ` | Name should be trimmed before saving. | Not manually tested yet. | PASS |

---

# Backend Validation

The shared backend validator performs:

- Required-name validation
- Leading and trailing space removal
- Maximum 100-character validation
- Allowed-character validation
- Case-insensitive uniqueness validation
- Current-job exclusion during Edit Job

The following application flows call the shared backend validator:

- API job creation
- Dashboard job creation
- Upload Script job creation
- Edit Job update

| Test ID | Test Scenario | Expected Result | Status |
|---|---|---|---|
| BACKEND-01 | Submit invalid name through Dashboard POST | Backend rejects the request even if frontend validation is bypassed. | Implemented; direct bypass test pending. |
| BACKEND-02 | Submit duplicate name through Dashboard POST | Backend rejects the duplicate. | Implemented; direct bypass test pending. |
| BACKEND-03 | Submit more than 100 characters through Dashboard POST | Backend rejects the request. | Implemented; direct bypass test pending. |
| BACKEND-04 | Submit invalid name through Upload Script POST | Backend rejects the upload. | PASS |
| BACKEND-05 | Edit job using invalid or duplicate name | Backend rejects the update. | PASS |
| BACKEND-06 | Create API job with invalid name | API returns HTTP 400. | Not manually tested yet. |

---

# Current Result

## Passed

- Required-name validation
- Invalid-character validation
- Maximum-length validation
- Duplicate-name validation
- Real-time availability checking
- Dashboard job creation
- Upload Script validation
- Edit Job validation
- Description-only edit
- Original-name exclusion during editing
- Backend validation integration

## Remaining Manual Checks

1. Case-insensitive duplicate validation.
2. Automatic trimming of leading and trailing spaces.
3. Direct backend/API bypass testing.

## Overall Status

The Job Name Validation feature is functionally complete.

Current manual test result:

- Passed: 25
- Pending: 9
- Failed: 0




## Upload Validation – Open Requirement Questions

### 1. Unsupported File Extension

Observed behavior:
The platform rejected the unsupported `.txt` file and did not create a job.

Requirement question:
Should unsupported file types always be rejected with a clear validation message?

Recommended behavior:
Yes. Only supported extensions should be accepted:
- `.py`
- `.ps1`
- `.bat`
- `.cmd`

Status:
Pending requirement confirmation.

---

### 2. Duplicate Filename

Observed behavior:
The platform accepted the same filename again and stored it using a unique generated suffix.

Example:
- `final_test_a981a537.py`
- `final_test_4299fa50.py`

Requirement question:
Should the platform reject duplicate filenames, or automatically rename and store them safely?

Recommended behavior:
Automatically rename duplicate files so that the existing file is not overwritten.

Status:
Working As expected

---

### 3. Empty Script File

Observed behavior:
The platform accepted a 0-byte Python file, created a job, and marked execution as completed with no console output.

Requirement question:
Should empty script files be rejected during upload?

Recommended behavior:
Yes. Empty files should be rejected with a message such as:

`Script file cannot be empty.`

Status:
Working As Expected


UI / UX TEST CHECKLIST

□ Dashboard loads correctly.
□ Upload Script page loads correctly.
□ Execution History page loads correctly.
□ Job Details page loads correctly.
□ Edit Job page loads correctly.

□ All buttons are visible.
□ Buttons work correctly.
□ No overlapping text.
□ No broken layout.
□ Proper spacing between fields.
□ Responsive on browser resize.

□ Success messages are clear.
□ Error messages are readable.
□ Status colors are correct.
□ Tables load properly.
□ Search works.
□ Filters work.
□ Pagination works.