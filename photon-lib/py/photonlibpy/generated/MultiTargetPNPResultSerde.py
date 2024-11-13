###############################################################################
## Copyright (C) Photon Vision.
###############################################################################
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <https://www.gnu.org/licenses/>.
###############################################################################

###############################################################################
## THIS FILE WAS AUTO-GENERATED BY ./photon-serde/generate_messages.py.
##                        --> DO NOT MODIFY <--
###############################################################################

from typing import TYPE_CHECKING

from ..packet import Packet
from ..targeting import *  # noqa

if TYPE_CHECKING:
    from ..targeting import MultiTargetPNPResult  # noqa
    from ..targeting import PnpResult  # noqa


class MultiTargetPNPResultSerde:
    # Message definition md5sum. See photon_packet.adoc for details
    MESSAGE_VERSION = "541096947e9f3ca2d3f425ff7b04aa7b"
    MESSAGE_FORMAT = "PnpResult:ae4d655c0a3104d88df4f5db144c1e86 estimatedPose;int16 fiducialIDsUsed[?];"

    @staticmethod
    def pack(value: 'MultiTargetPNPResult' ) -> 'Packet':
        ret = Packet()

        # estimatedPose is of non-intrinsic type PnpResult
        ret.encodeBytes(PnpResult.photonStruct.pack(value.estimatedPose).getData())

        # fiducialIDsUsed is a custom VLA!
        ret.encodeShortList(value.fiducialIDsUsed)
        return ret


    @staticmethod
    def unpack(packet: 'Packet') -> 'MultiTargetPNPResult':
        ret = MultiTargetPNPResult()

        # estimatedPose is of non-intrinsic type PnpResult
        ret.estimatedPose = PnpResult.photonStruct.unpack(packet)

        # fiducialIDsUsed is a custom VLA!
        ret.fiducialIDsUsed = packet.decodeShortList()

        return ret


# Hack ourselves into the base class
MultiTargetPNPResult.photonStruct = MultiTargetPNPResultSerde()