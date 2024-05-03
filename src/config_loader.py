from yaml import safe_load

def load_config(*keys: str):
    with open('config.yaml', 'r', encoding='utf-8') as f:
        data: dict = safe_load(f)
        
    for key in keys:
        data = data.get(key, None)
        
        if data is None:
            return None
        
    return data