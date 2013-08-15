# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class GPUDevice(object):
  """Provides information about an individual GPU device.

     On platforms which support them, the vendor_id and device_id are
     PCI IDs. On other platforms, the vendor_string and device_string
     are platform-dependent strings.
  """

  def __init__(self, vendor_id, device_id, vendor_string, device_string):
    self._vendor_id = vendor_id
    self._device_id = device_id
    self._vendor_string = vendor_string
    self._device_string = device_string

  @classmethod
  def FromDict(cls, attrs):
    """Constructs a GPUDevice from a dictionary. Requires the
       following attributes to be present in the dictionary:

         vendor_id
         device_id
         vendor_string
         device_string

       Raises an exception if any attributes are missing.
    """
    return cls(attrs["vendor_id"], attrs["device_id"],
               attrs["vendor_string"], attrs["device_string"])

  @property
  def vendor_id(self):
    """The GPU vendor's PCI ID as a number, or 0 if not available.

       Most desktop machines supply this information rather than the
       vendor and device strings."""
    return self._vendor_id

  @property
  def device_id(self):
    """The GPU device's PCI ID as a number, or 0 if not available.

       Most desktop machines supply this information rather than the
       vendor and device strings."""
    return self._device_id

  @property
  def vendor_string(self):
    """The GPU vendor's name as a string, or the empty string if not
       available.

       Most mobile devices supply this information rather than the PCI
       IDs."""
    return self._vendor_string

  @property
  def device_string(self):
    """The GPU device's name as a string, or the empty string if not
       available.

       Most mobile devices supply this information rather than the PCI
       IDs."""
    return self._device_string
