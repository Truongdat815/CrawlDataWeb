"""
Data validation using schemas
Validates data against schema definitions before storage
"""


def validate_against_schema(data, schema, strict=False):
    """
    Validate data against schema
    
    Args:
        data: dict to validate
        schema: schema dict with field names
        strict: True = require all fields, False = allow None values
    
    Returns:
        dict: validated data (only fields in schema)
    
    Raises:
        ValueError: if missing required fields or invalid type
    """
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict, got {type(data)}")
    
    validated = {}
    required_fields = list(schema.keys())
    
    # Check required fields
    missing = []
    for f in required_fields:
        if f not in data:
            missing.append(f)
    
    if missing and strict:
        raise ValueError(f"Missing required fields: {missing}")
    
    # Map to schema (include all fields, even if None)
    for field_name in schema.keys():
        if field_name in data:
            validated[field_name] = data[field_name]
        else:
            validated[field_name] = None
    
    return validated


def serialize_for_response(data, schema):
    """
    Serialize data for API response (only fields in schema)
    
    Args:
        data: dict from database
        schema: schema dict
    
    Returns:
        dict: serialized data with only schema fields
    """
    if not isinstance(data, dict):
        return {}
    
    return {k: data.get(k) for k in schema.keys()}


def get_schema_fields(schema):
    """Get list of all fields in schema"""
    return list(schema.keys())


def check_required_fields(data, required_fields):
    """
    Check if data has all required fields
    
    Args:
        data: dict to check
        required_fields: list of field names
    
    Returns:
        tuple: (is_valid, missing_fields)
    """
    missing = [f for f in required_fields if f not in data or data.get(f) is None]
    return len(missing) == 0, missing
