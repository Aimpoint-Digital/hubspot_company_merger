# Merge Hubspot Companies

## Description
This application allows you to merge pairs of Hubspot companies. The application handles the removal of child/parent company associations before merging, and the re-association of child/parent companies after merging.

## Pre-requirements
Python needs to be installed on the machine that is running this application. You can download Python at https://www.python.org/downloads/release/python-3121/

**IMPORTANT**: Make sure you check the checkbox that says "Add Python 3.# to PATH" on the first window of the installer.

## Preparing the data input file
To use this application, you need to provide a data input CSV file. This file should be called `input_data.csv`, and should be stored in the root of the application folder. The file should contain four columns:
- `id`: The Hubspot identifier of the company
- `company_name`: The name of the company
- `key`: This is the grouping identifier for pairs of companies that you want to group together. It should be a number. A given key should only be associated with two records.
- `action`: This determines which company should be kept and which company should be merged into the kept company. The values for this field should be only "keep" or "merge" (both lowercase)

An example `input_data.csv` is included in the application folder, and looks like:
```
id,company_name,key,action
18471734073,Aimpoint Digital,1,merge
18471728513,Aimpoint Digital - Enterprise,1,keep
18471734054,MyCompany,2,merge
18471728532,MyCompany Inc,2,keep
```

This file aims to:
- Merge "Aimpoint Digital" (18471734073) into "Aimpoint Digital - Enterprise" (18471728513). These are grouped together by `key`=1.
- Merge "MyCompany" (18471734054) into "MyCompany Inc" (18471728532). These are grouped together by `key`=2.

## Data input file validation
There is a check at the beginning of the application to ensure that the CSV is valid. These checks include:
- Checks for duplicate records accross the file
- Checks for conflicting associations (e.g. company A should be merged with company B, company A should be merged with company C)
- Each key is associated with only two records
- Each key is associated with one "keep" and one "merge" record, designated by the `action` field
- The `action` field only contains the values "keep" and "merge". 

If these validation checks are breached, you will be notified. The CSV file will need to pass validation before the application will run.

## Running the application
Double click the `run.bat` file to start the application. You will be prompted for your Hubspot API key. The data input file will then be validated, and you will be asked if you wish to continue with the merge. Enter `y` and then press Enter to continue.