from photonvision.targeting import TimeSyncClient, TimeSyncServer

import pytest
import time


@pytest.fixture
def server() -> TimeSyncServer:
    s = TimeSyncServer(5812)
    yield s
    s.stop()


@pytest.fixture
def client() -> TimeSyncClient:
    c = TimeSyncClient("127.0.0.1", 5812, 0.100)
    yield c
    c.stop()


def test_TimeSyncProtocol(server, client) -> None:
    server.start()
    client.start()

    for i in range(10):
        time.sleep(0.1)
        m = client.getMetadata()
        if i == 0:
            # values aren't set on first loop
            continue
        assert m.offset != 0 and m.rtt2 != 0
        print(f"Offset={m.offset} rtt={m.rtt2}")
