import pytest
from photonlibpy import Packet, PhotonCamera
from photonlibpy.simulation import PhotonCameraSim
from photonlibpy.targeting import PhotonPipelineResult
from ntcore import NetworkTableInstance

import photonlibpy

from wpilib import Timer
from wpimath.geometry import Rotation2d

from photonvision.targeting import TimeSyncClient

import time


def waitForCondition(name: str, condition) -> None:
    # wait up to 1 second for satisfaction
    for i in range(100):
        if condition():
            print(f"{name} satisfied on iteration {i}")
            return
        time.sleep(0.01)
    raise Exception(f"{name} was never satisfied")


def waitForSequenceNumber(camera: PhotonCamera, seq: int) -> PhotonPipelineResult:
    # assert camera._heartbeatEntry.getTopic().getHandle() != 0

    print(f"Waiting for seq={seq} on {camera._heartbeatEntry.getTopic().getName()}")
    # wait up to 1 second for a new result
    for i in range(100):
        results = camera.getAllUnreadResults()
        for res in results:
            print(res)
            if res.metadata.sequenceID == seq:
                return res

        time.sleep(0.01)
    raise Exception(f"Never saw sequence number {seq}")


@pytest.fixture
def nt():
    robotNt = NetworkTableInstance.create()
    coprocNt = NetworkTableInstance.create()
    yield (robotNt, coprocNt)
    robotNt.flush()
    coprocNt.flush()
    robotNt.stopServer()
    coprocNt.stopClient()
    NetworkTableInstance.destroy(robotNt)
    NetworkTableInstance.destroy(coprocNt)


@pytest.fixture
def robotNtRestart():
    nt = NetworkTableInstance.create()
    yield nt
    nt.flush()
    nt.stopServer()
    NetworkTableInstance.destroy(nt)


@pytest.fixture
def coprocNtRestart():
    nt = NetworkTableInstance.create()
    yield nt
    nt.flush()
    nt.stopClient()
    NetworkTableInstance.destroy(nt)


def test_nt(nt) -> None:
    robotNt, coprocNt = nt

    robotNt.startServer("networktables_random.json", "", 15941, 15940)
    coprocNt.setServer("127.0.0.1", 15940)
    coprocNt.startClient4("testClient")

    time.sleep(1.0)
    assert len(coprocNt.getConnections()) == 1
    assert len(robotNt.getConnections()) == 1

    coprocSubTable = coprocNt.getTable("foo").getSubTable("bar")
    robotSubTable = robotNt.getTable("foo").getSubTable("bar")

    robotSubscriber = robotSubTable.getIntegerTopic("baz").subscribe(0)

    coprocPublisher = coprocSubTable.getIntegerTopic("baz").publish()
    coprocPublisher.set(42)

    time.sleep(0.5)
    assert robotSubscriber.get() == 42


def test_Empty() -> None:
    packet = Packet(b"1")
    PhotonPipelineResult()
    packet.setData(bytes(0))
    PhotonPipelineResult.photonStruct.unpack(packet)
    # There is no need for an assert as we are checking
    # if this throws an exception (it should not)


@pytest.mark.skip
def test_TimeSyncServerWithPhotonCamera() -> None:
    camera = PhotonCamera("Arducam_OV2311_USB_Camera")
    photonlibpy.photonCamera.setVersionCheckEnabled(False)

    for i in range(5):
        time.sleep(0.500)

        res = camera.getLatestResult()
        captureTime = res.getTimestampSeconds()
        now = Timer.getFPGATimestamp()

        assert captureTime < now

        print(
            f"sequence {res.metadata.sequenceID} image capture {captureTime} received at {res.getTimestampSeconds()} now: {Timer.getFPGATimestamp()} time since last pong: {res.metadata.timeSinceLastPong / 1e6}"
        )


@pytest.fixture
def tspClient() -> TimeSyncClient:
    tsp = TimeSyncClient("127.0.0.1", 5810, 0.5)
    yield tsp
    tsp.stop()


# @pytest.mark.skip
@pytest.mark.parametrize(
    "robotStart, coprocStart, robotRestart, coprocRestart",
    [
        [1, 10, 30, 30],
        [10, 2, 30, 30],
        [10, 10, 30, 30],
        # Reboot just the coproc
        [1, 1, 30, 10],
        # Reboot just the robot
        [1, 1, 10, 30],
    ],
)
def test_RestartingRobotandCoproc(
    robotStart: int,
    coprocStart: int,
    robotRestart: int,
    coprocRestart: int,
    tspClient,
    nt,
    robotNtRestart,
    coprocNtRestart,
):
    robotNt, coprocNt = nt

    robotNt.addLogger(10, 255, lambda it: print(f"ROBOT: {it.data.message}"))
    coprocNt.addLogger(10, 255, lambda it: print(f"CLIENT: {it.data.message}"))

    robotCamera = PhotonCamera("MY_CAMERA", robotNt)

    # apparently need a PhotonCamera to hand down
    fakePhotonCoprocCam = PhotonCamera("MY_CAMERA", coprocNt)
    coprocSim = PhotonCameraSim(fakePhotonCoprocCam)
    coprocSim.prop.setCalibrationFromFOV(640, 480, Rotation2d.fromDegrees(90))
    coprocSim.prop.setFPS(30)
    coprocSim.setMinTargetAreaPixels(20.0)

    for i in range(20):
        seq = i + 1

        if i == coprocRestart:
            print("Restarting coprocessor NT client")

            coprocNt.stopClient()
            NetworkTableInstance.destroy(coprocNt)
            coprocNt = coprocNtRestart
            coprocNt.addLogger(
                10, 255, lambda it: print(f"CLIENT RESTARTED: {it.data.message}")
            )

            fakePhotonCoprocCam = PhotonCamera("MY_CAMERA", coprocNt)
            coprocSim = PhotonCameraSim(fakePhotonCoprocCam)
            coprocSim.prop.setCalibrationFromFOV(640, 480, Rotation2d.fromDegrees(90))
            coprocSim.prop.setFPS(30)
            coprocSim.setMinTargetAreaPixels(20.0)
            time.sleep(0.100)

        if i == robotRestart:
            print("Restarting robot NT server")

            robotNt.stopServer()
            NetworkTableInstance.destroy(robotNt)
            time.sleep(0.100)
            robotNt = robotNtRestart
            robotNt.addLogger(
                10, 255, lambda it: print(f"ROBOT RESTARTED: {it.data.message}")
            )
            robotCamera = PhotonCamera("MY_CAMERA", robotNt)
            time.sleep(0.100)

        if i == coprocStart or i == coprocRestart:
            coprocNt.setServer("127.0.0.1", 15940)
            coprocNt.startClient4("testClient")
            time.sleep(0.100)

            # PhotonCamera makes a server by default - connect to it
            tspClient.start()

        if i == robotStart or i == robotRestart:
            robotNt.startServer("networktables_random.json", "", 15941, 15940)
            time.sleep(0.100)

        if i == max(coprocStart, robotStart) or i == robotRestart or i == coprocRestart:

            def getConnections(processor):
                def func():
                    return len(processor.getConnections()) == 1

                return func

            waitForCondition("Coproc connection", getConnections(coprocNt))
            waitForCondition("Rio connection", getConnections(robotNt))
            time.sleep(0.1)

        result1 = PhotonPipelineResult()
        result1.metadata.captureTimestampMicros = seq * 100
        result1.metadata.publishTimestampMicros = seq * 150
        result1.metadata.sequenceID = seq
        if tspClient is not None:
            result1.metadata.timeSinceLastPong = tspClient.getMetadata().lastPongTime
        else:
            result1.metadata.timeSinceLastPong = 2**31

        coprocSim.submitProcessedFrame(result1)
        coprocNt.flush()

        if i > robotStart and i > coprocStart:
            ret = waitForSequenceNumber(robotCamera, seq)

        # force verifyVersion to do checks
        robotCamera._lastVersionCheckTime = -100
        robotCamera._prevTimeSyncWarnTime = -100
        # There is no need for an assert as we are checking
        # if this throws an exception (it should not)
        robotCamera._versionCheck()

    time.sleep(1.0)
