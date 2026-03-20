import json
import os
import re

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from palaver.app.constants import ENV_FILE


router = APIRouter(prefix="/api/keys", tags=["keys"])


class EditKeyRequest(BaseModel):
    name: str
    value: str


@router.get("")
def list_api_keys() -> list[str]:
    api_key_vars = [k[:-len("_API_KEY")] for k in os.environ.keys() if k.endswith("_API_KEY")]
    return api_key_vars


@router.post("")
def add_or_edit_api_key(request: EditKeyRequest):
    key_name, value = request.name.upper(), request.value
    var_name = f"{key_name}_API_KEY"
    value_json = json.dumps(value, ensure_ascii=False)

    with open(ENV_FILE) as f:
        env_file = f.read()
    
    if var_name not in os.environ:
        prefix = "" if env_file.endswith("\n") else "\n"
        with open(ENV_FILE, "a") as f:
            f.write(f"{prefix}{var_name}={value_json}")
        os.environ[var_name] = value
        return
    
    if os.environ[var_name] == value:
        return
    
    pattern = rf"^{var_name}=([\"'])(.*?)(\1)$"
    subsitute = rf"{var_name}={value_json}"
    new_env_file = re.sub(pattern, subsitute, env_file, flags=re.M)
    print(new_env_file)
    if new_env_file == env_file:
        new_env_file = f"{new_env_file.strip()}\n{var_name}={value_json}\n"
    
    with open(ENV_FILE, "w") as f:
        f.write(new_env_file)
    os.environ[var_name] = value


@router.delete("/{key_name}")
def delete_api_key(key_name: str):
    key_name = key_name.upper()
    availble_keys = list_api_keys()
    if key_name not in availble_keys:
        raise HTTPException(404, f"API key '{key_name}' not found.")
    
    var_name = f"{key_name}_API_KEY"

    with open(ENV_FILE) as f:
        env_file = f.read()

    pattern = rf"^{var_name}=([\"'])(.*?)(\1)$\n?"
    new_env_file = re.sub(pattern, "", env_file, flags=re.M)
    
    with open(ENV_FILE, "w") as f:
        f.write(new_env_file)

    os.environ.pop(var_name)