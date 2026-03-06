from fastapi import APIRouter, HTTPException

from palaver.app.config import ProviderConfig
from palaver.app.constants import SUPPORTED_SERVICES
from palaver.app.dataclasses.agent import CreateProviderRequest, DeleteResponse
from palaver.app.services.agent_service import get_agent_service


providers_router = APIRouter()
agent_service = get_agent_service()


@providers_router.get("/", response_model=list[ProviderConfig])
async def list_providers():
    """List all providers"""
    return agent_service.llm_config.providers

@providers_router.get("/{provider_name}", response_model=ProviderConfig)
async def get_single_provider(provider_name: str):
    """Get a specific provider"""
    agent = agent_service.get_provider(provider_name)
    if not agent:
        raise HTTPException(status_code=404, detail="Provider not found")
    return agent

@providers_router.post("/", response_model=ProviderConfig)
async def create_provider(request: CreateProviderRequest):
    """Create a new provider"""
    provider = agent_service.create_provider(ProviderConfig.model_validate(request.model_dump()))
    if provider is None:
        raise HTTPException(status_code=400, detail="Provider already exists")
    else:
        return provider

@providers_router.put("/{provider_name}", response_model=ProviderConfig)
async def update_provider(provider_name: str, request: CreateProviderRequest):
    """Update an existing provider"""
    if provider_name != request.name:
        raise HTTPException(status_code=400, detail="Cannot change provider name")
        
    success = agent_service.update_provider_config(provider_name, request.model_dump())
    if not success:
        raise HTTPException(status_code=404, detail="Provider not found")
        
    return agent_service.get_provider(provider_name)

@providers_router.delete("/{provider_name}", response_model=DeleteResponse)
async def delete_provider(provider_name: str):
    """Delete a provider"""
    success = agent_service.delete_provider(provider_name)
    if success:
        return DeleteResponse(success=True, message="Provider deleted successfully")
    else:
        raise HTTPException(status_code=400, detail="Cannot delete provider - either not found or in use by agents")

@providers_router.get("/{provider_name}/models", response_model=list[str])
async def list_models(provider_name: str):
    try:
        return await agent_service.list_models(provider_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Provider not found") from e

services_router = APIRouter()
@services_router.get("/", response_model=list[str])
async def list_supported_services():
    return SUPPORTED_SERVICES

router = APIRouter(prefix="/api", tags=["providers"])
router.include_router(providers_router, prefix="/providers")
router.include_router(services_router, prefix="/provider-services")