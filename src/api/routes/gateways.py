"""Gateway asset registry routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.dependencies import get_gateway_repository
from src.api.schemas import GatewayMetadataResponse
from src.data.repository import GatewayRepository

router = APIRouter(prefix="/gateways", tags=["Gateways"])


@router.get("", response_model=list[GatewayMetadataResponse])
def list_gateways(
    tenant: str | None = Query(None, description="Filter by tenant name"),
    site_type: str | None = Query(None, description="Filter by installation site type"),
    gateway_repo: GatewayRepository = Depends(get_gateway_repository),
) -> list[GatewayMetadataResponse]:
    """Retrieve list of registered radio gateways with optional filtering."""
    results = gateway_repo.list_gateways(tenant=tenant, site_type=site_type)
    return [GatewayMetadataResponse(**r) for r in results]


@router.get("/{gateway_id}", response_model=GatewayMetadataResponse)
def get_gateway_metadata(
    gateway_id: str = Path(..., examples=["0A2778A31BE3"], description="Gateway Identifier"),
    gateway_repo: GatewayRepository = Depends(get_gateway_repository),
) -> GatewayMetadataResponse:
    """Retrieve asset registry metadata for a single gateway."""
    data = gateway_repo.find_by_id(gateway_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway '{gateway_id}' not found in master asset registry.",
        )
    return GatewayMetadataResponse(**data)
