import uvicorn

from datetime import datetime
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dmrtools.dispatcher import Dispatcher


class DMRApiHelper:
    CALLS_MAX = 50

    dispatcher: Dispatcher|None = None

    @classmethod
    def get_peers(cls) -> list:
        if cls.dispatcher is None:
            return list()

        peers = sorted(cls.dispatcher.peer_keeper.peers,
                       key=lambda p: p.connect_time)

        peers_info = [{
            "name": p.name,
            "peer_id": p.peer_id,
            "addr": p.addr_str,
            "status": p.status.name,
            "connect_time": p.connect_time,
            "active_time": p.active_time,
            "units": list(p.units.keys()),
            "config": p.config} for p in peers]

        return peers_info

    @classmethod
    def get_calls(cls) -> list:
        if cls.dispatcher is None:
            return list()

        calls = sorted(cls.dispatcher.call_keeper.calls_log,
                       key=lambda c: c.start_time, reverse=True)

        # get first CALLS_MAX if more than
        if len(calls) > cls.CALLS_MAX:
            calls = calls[:cls.CALLS_MAX]

        calls_info = [{
            "call_id": c.call_id,
            "dir": f"{c.src_id}->{c.dst_hr}",
            "src_id": c.src_id,
            "dst_id": c.dst_id,
            "peer_id": c.peer_id,
            "call_type": c.call_type.name,
            "start_time": c.start_time,
            "last_packet_time": c.last_packet_time,
            "is_ended": c.is_ended,
            "end_time": c.end_time,
            "broadcast": c.route_to is None,
            "route_to": (list(peer.name for peer in c.route_to)
                         if c.route_to is not None else []),
            "time": f"{c.time:.1f}s"} for c in calls]

        return calls_info


# Define FastAPI app
app = FastAPI()


# Mount the "dashboard" directory at /dashboard
app.mount("/dashboard", StaticFiles(directory="dashboard"), name="dashboard")


@app.get("/api/dashboard")
async def get_dashboard():
    return {"success": True,
            "peers": DMRApiHelper.get_peers(),
            "calls": DMRApiHelper.get_calls()}


@app.get("/api/peers")
async def get_peers():
    return {"success": True, "peers": DMRApiHelper.get_peers()}


@app.get("/api/calls")
async def get_calls():
    return {"success": True, "calls": DMRApiHelper.get_calls()}


async def start_api(host: str, port: int, dispatcher: Dispatcher) -> None:
    DMRApiHelper.dispatcher = dispatcher
    config = uvicorn.Config(app, host=host, port=port, log_level="error",
                            loop="asyncio")
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except Exception as e:
        print(f"start_api: Exception {e}")
