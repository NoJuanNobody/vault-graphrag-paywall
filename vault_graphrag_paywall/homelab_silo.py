"""Homelab Per-Business Siloed VM & Nested Docker Compose Provisioner (~$130 Mini PC + 10TB External Drive)."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


def _sanitize_slug(raw_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\-]+", "-", raw_id.strip().lower()).strip("-")
    return slug or "default-business"


@dataclass
class VMSiloSpec:
    """Per-business isolated Virtual Machine specification on the ~$130 Mini PC + 10TB external drive."""

    business_id: str
    vm_name: str
    vcpus: int
    ram_gb: int
    storage_slice_gb: int
    storage_mount_path: str
    vlan_id: int
    subnet_cidr: str
    api_port: int = 8001
    web_port: int = 3001
    hypervisor_host: str = "Room-Homelab-MiniPC-$130 + 10TB-External-Drive"
    nested_docker_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HomelabSiloProvisioner:
    """Provisions strictly isolated Per-Business VMs and nested Docker Compose stacks on a ~$130 Mini PC + 10TB drive."""

    def __init__(
        self,
        host_cost_usd: float = 130.0,
        total_storage_tb: float = 10.0,
        total_vcpus: int = 8,
        total_ram_gb: int = 16,
        external_drive_mount: str = "/mnt/homelab-10tb-vaults",
    ) -> None:
        self.host_cost_usd = host_cost_usd
        self.total_storage_tb = total_storage_tb
        self.total_storage_gb = int(total_storage_tb * 1000)
        self.total_vcpus = total_vcpus
        self.total_ram_gb = total_ram_gb
        self.external_drive_mount = external_drive_mount.rstrip("/")
        self.silos: Dict[str, VMSiloSpec] = {}
        self._next_vlan_id = 101

    @property
    def allocated_storage_gb(self) -> int:
        return sum(s.storage_slice_gb for s in self.silos.values())

    @property
    def available_storage_gb(self) -> int:
        return self.total_storage_gb - self.allocated_storage_gb

    def provision_vm_silo(
        self,
        business_id: str,
        vcpus: int = 2,
        ram_gb: int = 4,
        storage_gb: int = 500,
        api_port: int = 8001,
        web_port: int = 3001,
    ) -> VMSiloSpec:
        """Create an isolated VM specification with dedicated storage slice on the 10TB drive and isolated VLAN."""
        slug = _sanitize_slug(business_id)
        if slug in self.silos:
            return self.silos[slug]

        if storage_gb <= 0:
            raise ValueError("storage_gb must be positive")
        if storage_gb > self.available_storage_gb:
            raise ValueError(
                f"Requested {storage_gb}GB exceeds remaining 10TB drive capacity ({self.available_storage_gb}GB)"
            )

        vlan_id = self._next_vlan_id
        self._next_vlan_id += 1
        octet = vlan_id % 255

        spec = VMSiloSpec(
            business_id=slug,
            vm_name=f"vm-silo-{slug}",
            vcpus=vcpus,
            ram_gb=ram_gb,
            storage_slice_gb=storage_gb,
            storage_mount_path=f"{self.external_drive_mount}/silos/{slug}",
            vlan_id=vlan_id,
            subnet_cidr=f"10.200.{octet}.0/24",
            api_port=api_port,
            web_port=web_port,
        )
        self.silos[slug] = spec
        return spec

    def generate_docker_compose(
        self,
        business_id: str,
        port: int = 8001,
        web_port: int = 3001,
        storage_gb: int = 500,
    ) -> str:
        """Generate a nested Docker Compose YAML configuration strictly isolated inside the business's VM."""
        slug = _sanitize_slug(business_id)
        spec = self.silos.get(slug)
        if spec is None:
            spec = self.provision_vm_silo(
                business_id=slug,
                storage_gb=storage_gb,
                api_port=port,
                web_port=web_port,
            )

        compose_yaml = f"""version: "3.9"
# Per-Business Siloed Nested Docker Stack inside VM: {spec.vm_name}
# Hardware Host: {spec.hypervisor_host} (VLAN {spec.vlan_id}, Subnet {spec.subnet_cidr})
services:
  vault-graphrag-api-{slug}:
    image: ghcr.io/nojuannobody/vault-graphrag-paywall:latest
    container_name: silo-{slug}-api
    restart: unless-stopped
    ports:
      - "{port}:{port}"
    environment:
      - BUSINESS_ID={slug}
      - API_PORT={port}
      - WEB_PORT={web_port}
      - VENDING_PRICE_USD=0.05
      - DATABASE_URL=sqlite:////data/ledger/vault_paywall_{slug}_{port}.db
      - VAULT_PATH=/data/obsidian-vault
    volumes:
      - {spec.storage_mount_path}/obsidian-vault:/data/obsidian-vault:ro
      - {spec.storage_mount_path}/ledger:/data/ledger:rw
    networks:
      - silo_net_{slug}
    security_opt:
      - no-new-privileges:true

  vault-vending-web-{slug}:
    image: ghcr.io/nojuannobody/vault-graphrag-web:latest
    container_name: silo-{slug}-web
    restart: unless-stopped
    ports:
      - "{web_port}:{web_port}"
    environment:
      - BUSINESS_ID={slug}
      - WEB_PORT={web_port}
      - API_URL=http://vault-graphrag-api-{slug}:{port}
    depends_on:
      - vault-graphrag-api-{slug}
    networks:
      - silo_net_{slug}

networks:
  silo_net_{slug}:
    driver: bridge
    ipam:
      config:
        - subnet: {spec.subnet_cidr}
"""
        return compose_yaml

    def get_hardware_summary(self) -> Dict[str, Any]:
        """Return homelab server capacity and active VM silo allocations."""
        return {
            "hardware_profile": "~$130 Mini PC (Intel N100/Ryzen) + 10TB External Drive",
            "host_cost_usd": self.host_cost_usd,
            "total_storage_tb": self.total_storage_tb,
            "total_storage_gb": self.total_storage_gb,
            "allocated_storage_gb": self.allocated_storage_gb,
            "available_storage_gb": self.available_storage_gb,
            "active_silos_count": len(self.silos),
            "silos": [s.to_dict() for s in self.silos.values()],
        }
