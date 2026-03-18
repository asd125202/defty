# Copyright (c) 2026 APRL Technologies Inc. All rights reserved.
# Author: Yiju Li
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Defty — Physical AI IDE for robot intelligence development."""

import os

# Disable OpenCV's obsensor backend globally.  The obsensor UVC driver probes
# every camera index on open, producing noisy "[ERROR] obsensor_uvc_stream_channel"
# messages and — critically — interfering with simultaneous camera access on
# Windows (camera N fails to open while camera M is already streaming).
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_OBSENSOR", "0")

from defty.__version__ import __version__

__all__ = ["__version__"]