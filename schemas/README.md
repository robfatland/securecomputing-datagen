# schemas/

Output schema definitions. Will contain:
- Patient record schema (fields, types, constraints)
- Clinical data schema (encounters, diagnoses, labs, medications)
- File format specifications (CSV headers, Parquet schema, or FHIR resource definitions)
- Validation rules (what constitutes a valid generated record)
- Mapping to the 18 HIPAA identifiers (which fields simulate which identifier types)
