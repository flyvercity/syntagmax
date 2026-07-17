Purpose / Meaning:

Adds or removes standard fields of the [FIELD] format inside requirement blocks

Adds or removes attributes in the YAML block of requirements

Works recursively across all Markdown files in the selected section

Can be used for the mass addition of service attributes, for example: source, status, owner

Supports value substitution via replace (updates existing values and adds missing ones)

Can substitute doors_id from a CSV file based on ext_id, where the ID attribute name is taken from attr_name in the .config/config.yaml section

Parameters:

-o, --operation — the operation to perform: add, del, or replace (default is add)

-t, --type — the type of change: field or attr (default is attr)

-n, --name — the name of the field or attribute

-l, --value — the value for the field or attribute being added

-c, --config — the path to vaults.yaml (default is ./config/vaults.yaml)

-v, --vault — the name of the vault in vaults.yaml (required parameter)

-s, --section — the name of the section in .config/config.yaml (required parameter)

--doors-csv — the path to the CSV file with ext_id and doors_id columns (default is ../docs/doors-ids.csv); if this parameter is passed, the value is taken from the mapping based on the current requirement's ext_id