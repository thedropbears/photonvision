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
        res = camera.getLatestResult()
        if res.metadata.sequenceID == seq:
            return res

        time.sleep(0.01)
    raise Exception(f"Never saw sequence number {seq}")


@pytest.fixture(autouse=True)
def setupCommon() -> None:
    pass


def test_Empty() -> None:
    packet = Packet(b"1")
    PhotonPipelineResult()
    packet.setData(bytes(0))
    PhotonPipelineResult.photonStruct.unpack(packet)
    # There is no need for an assert as we are checking
    # if this throws an exception (it should not)


@pytest.mark.skip
def test_TimeSyncServerWithPhotonCamera() -> None:
    NetworkTableInstance.getDefault().stopClient()
    NetworkTableInstance.getDefault().startServer()

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


# @pytest.mark.skip
@pytest.mark.parametrize(
    "robotStart, coprocStart, robotRestart, coprocRestart",
    [
        [1, 10, 30, 30],
        [10, 2, 30, 30],
        [10, 10, 30, 30],
        # Reboot just the robot
        [1, 1, 10, 30],
        # Reboot just the coproc
        [1, 1, 30, 10],
    ],
)
def test_RestartingRobotandCoproc(
    robotStart: int, coprocStart: int, robotRestart: int, coprocRestart: int
):
    robotNt = NetworkTableInstance.create()
    coprocNt = NetworkTableInstance.create()

    robotNt.addLogger(10, 255, lambda it: print(f"ROBOT: {it.data.message}"))
    coprocNt.addLogger(10, 255, lambda it: print(f"CLIENT: {it.data.message}"))

    tspClient: TimeSyncClient | None = None

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

            fakePhotonCoprocCam.close()
            coprocNt.close()
            coprocNt = NetworkTableInstance.create()

            coprocNt.addLogger(10, 255, lambda it: print(f"CLIENT: {it.data.message}"))

            fakePhotonCoprocCam = PhotonCamera("MY_CAMERA", coprocNt)
            coprocSim = PhotonCameraSim(fakePhotonCoprocCam)
            coprocSim.prop.setCalibrationFromFOV(640, 480, Rotation2d.fromDegrees(90))
            coprocSim.prop.setFPS(30)
            coprocSim.setMinTargetAreaPixels(20.0)
        if i == robotRestart:
            print("Restarting robot NT server")

            robotNt.close()
            robotNt = NetworkTableInstance.create()
            robotNt.addLogger(10, 255, lambda it: print(f"ROBOT: {it.data.message}"))
            robotCamera = PhotonCamera("MY_CAMERA", robotNt)

        if i == coprocStart or i == coprocRestart:
            coprocNt.setServer("127.0.0.1", 5940)
            coprocNt.startClient4("testClient")

            # PhotonCamera makes a server by default - connect to it
            tspClient = TimeSyncClient("127.0.0.1", 5810, 0.5)

        if i == robotStart or i == robotRestart:
            robotNt.startServer("networktables_random.json", "", 5941, 5940)

        time.sleep(0.100)

        if i == max(coprocStart, robotStart):

            def getConnections(processor):
                def func():
                    return len(processor.getConnections()) == 1

                return func

            waitForCondition("Coproc connection", getConnections(coprocNt))
            waitForCondition("Rio connection", getConnections(robotNt))

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
            coprocSim.submitProcessedFrame(result1)
            print(ret)

        # force verifyVersion to do checks
        robotCamera._lastVersionCheckTime = -100
        robotCamera._prevTimeSyncWarnTime = -100
        # There is no need for an assert as we are checking
        # if this throws an exception (it should not)
        robotCamera._versionCheck()

    coprocSim.close()
    coprocNt.close()
    robotNt.close()
    tspClient.stop()
