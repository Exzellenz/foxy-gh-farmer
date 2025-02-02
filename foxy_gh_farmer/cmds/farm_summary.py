import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional

import click
from chia.cmds.cmds_util import get_any_service_client
from chia.rpc.farmer_rpc_client import FarmerRpcClient
from chia.util.misc import format_bytes
from chia.util.network import is_localhost


@click.command("summary", short_help="Summary of farming information")
def summary_cmd() -> None:
    foxy_root: Path = Path(os.path.expanduser(os.getenv("FOXY_GH_ROOT", "~/.foxy-gh-farmer/mainnet"))).resolve()

    asyncio.run(print_farm_summary(foxy_root))


async def print_farm_summary(root_path: Path):
    harvesters_summary = await get_harvesters_summary(root_path)
    farmer_running = False if harvesters_summary is None else True  # harvesters uses farmer rpc too

    print("Farming status: ", end="")
    if not farmer_running:
        print("Not running")
    else:
        print("Farming")

    class PlotStats:
        total_plot_size = 0
        total_plots = 0

    if harvesters_summary is not None:
        harvesters_local: Dict[str, Dict[str, Any]] = {}
        harvesters_remote: Dict[str, Dict[str, Any]] = {}
        for harvester in harvesters_summary["harvesters"]:
            ip = harvester["connection"]["host"]
            if is_localhost(ip):
                harvesters_local[harvester["connection"]["node_id"]] = harvester
            else:
                if ip not in harvesters_remote:
                    harvesters_remote[ip] = {}
                harvesters_remote[ip][harvester["connection"]["node_id"]] = harvester

        def process_harvesters(harvester_peers_in: Dict[str, Dict[str, Any]]) -> None:
            for harvester_peer_id, harvester_dict in harvester_peers_in.items():
                syncing = harvester_dict["syncing"]
                if syncing is not None and syncing["initial"]:
                    print(f"   Loading plots: {syncing['plot_files_processed']} / {syncing['plot_files_total']}")
                else:
                    total_plot_size_harvester = harvester_dict["total_plot_size"]
                    plot_count_harvester = harvester_dict["plots"]
                    PlotStats.total_plot_size += total_plot_size_harvester
                    PlotStats.total_plots += plot_count_harvester
                    print(f"   {plot_count_harvester} plots of size: {format_bytes(total_plot_size_harvester)}")

        if len(harvesters_local) > 0:
            print(f"Local Harvester{'s' if len(harvesters_local) > 1 else ''}")
            process_harvesters(harvesters_local)
        for harvester_ip, harvester_peers in harvesters_remote.items():
            print(f"Remote Harvester{'s' if len(harvester_peers) > 1 else ''} for IP: {harvester_ip}")
            process_harvesters(harvester_peers)

        print(f"Plot count for all harvesters: {PlotStats.total_plots}")

        print("Total size of plots: ", end="")
        print(format_bytes(PlotStats.total_plot_size))
    else:
        print("Plot count: Unknown")
        print("Total size of plots: Unknown")


async def get_harvesters_summary(root_path: Path) -> Optional[Dict[str, Any]]:
    async with get_any_service_client(FarmerRpcClient, root_path=root_path) as node_config_fp:
        farmer_client, _ = node_config_fp
        if farmer_client is not None:
            return await farmer_client.get_harvesters_summary()
    return None
