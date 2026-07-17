
#################################################################################
#
# class `tubezb_cc2652_flasher`
#
#################################################################################

class tubezb_cc2652_flasher
  static CCFG_address = 0x057FD8
  static CCFG_reference = 0xC5FE0FC5    # DIO 15 for BSL

  #################################################################################
  # Flashing from Intel HEX files
  #################################################################################
  var filename          # filename of hex file
  var f                 # file object
  var file_checked       # was the file already parsed. It cannot be flashed if not previously parsed and validated
  var file_validated    # was the file already validated. It cannot be flashed if not previously parsed and validated
  var file_hex          # intelhex object
  var flasher           # low-level flasher object (cc2652_flasher instance)
  var _check_min_addr   # lowest address seen during check() — used to guard against partial HEX
  var _check_max_addr   # highest address+size seen during check()
  var _check_bytes      # total data bytes seen during check()

  def init()
    self.file_checked = false
    self.file_validated = false
  end

  def load(filename)
    import intelhex

    if type(filename) != 'string'   raise "value_error", "invalid file name" end
    self.filename = filename
    self.file_hex = intelhex(filename)    # prepare the parser object
    self.file_checked = false
    self.file_validated = false
  end

  #################################################################################
  # check that the HEX file is valid
  # parse it completely once, and verify some values
  #################################################################################
  def check()
    self.file_checked = false
    self.file_validated = false
    self.file_hex.parse(/ -> self._check_pre(),
                        / address, len, data, offset -> self._check_cb(address, len, data, offset),
                        / -> self._check_post()
                        )
  end

  #################################################################################
  # Flash the firmware to the device
  #
  #################################################################################
  def flash()
    if !self.file_checked
      print("FLH: firmware not checked, use `cc.check()`")
      raise "flash_error", "firmware not checked"
    end
    if !self.file_validated
      print("FLH: firmware not validated, use `cc.check()`")
      raise "flash_error", "firmware not validated"
    end

    import cc2652_flasher   # this stops zigbee and configures serial
    self.flasher = cc2652_flasher

    try
      self.file_hex.parse(/ -> self._flash_pre(),
                          / address, len, data, offset -> self._flash_cb(address, len, data, offset),
                          / -> self._flash_post()
                          )
    except .. as e, m
      self.file_checked = false
      self.file_validated = false
      raise e, m
    end
  end

  #################################################################################
  # Dump firmware to local file
  #
  #################################################################################
  def dump_to_file(filename)
    import cc2652_flasher   # this stops zigbee and configures serial
    self.flasher = cc2652_flasher
    print("FLH: Dump started (takes 3 minutes during which Tasmota is unresponsive)")
    self.flasher.start()
    self.flasher.ping()
    self.flasher.flash_dump_to_file(filename, 0x000000, 0x58000)
    print("FLH: Dump completed")
  end

  #################################################################################
  # low-level
  #################################################################################
  def _flash_pre()
    print("FLH: Flashing started (takes 5-8 minutes during which Tasmota is unresponsive)")
    self.flasher.start()
    self.flasher.ping()
    # erase flash
    self.flasher.flash_erase()
  end

  def _flash_post()
    print("FLH: Flashing completed: OK")
    var flash_crc = self.flasher.cmd_crc32(0x0,0x30000)
    print("FLH: Flash crc32 0x000000 - 0x2FFFF = " + str(flash_crc));
    # tasmota.log("FLH: Verification of HEX file OK", 2)
  end

  def _flash_cb(addr, sz, data, offset)
    var payload = data[offset .. offset + sz - 1]

    # final check
    if size(payload) != sz    raise "flash_error", "incomplete payload" end

    self.flasher.flash_write(addr, payload)
  end


  # start verification (log only)
  def _check_pre()
    self._check_min_addr = 0xFFFFFF
    self._check_max_addr = 0
    self._check_bytes = 0
    print("FLH: Starting verification of HEX file")
    # tasmota.log("FLH: Starting verification of HEX file", 2)
  end

  # don't flash so ignore data
  # check CCFG at location 0x57FD8 (4 bytes)
  def _check_cb(addr, sz, data, offset)
    # check than sz is a multiple of 4
    if (sz % 4 != 0)
      raise "value_error", format("size of payload is not a mutliple of 4: 0x%06X", addr)
    end

    # print(format("> addr=0x%06X sz=0x%02X data=%s", addr, sz, data[offset..offset+sz-1]))
    var CCFG = self.CCFG_address
    if addr < self._check_min_addr   self._check_min_addr = addr end
    if addr + sz > self._check_max_addr   self._check_max_addr = addr + sz end
    self._check_bytes += sz
    if addr <= CCFG && addr+sz >= CCFG+4
      # we have CCFG in the buffer
      var ccfg_bytes = data.get(4 + CCFG - addr, 4)

      if ccfg_bytes != self.CCFG_reference
        raise "value_error", format("incorrect CCFG, BSL is not set to DIO_15 LOW (0x%08X expected 0x%08X)", ccfg_bytes, self.CCFG_reference) end
      self.file_validated = true    # if we are here, it means that the file looks correct
    end
  end

  def _check_post()
    # Require both a 128KB+ address span AND 128KB+ of actual data bytes.
    # Span alone can be defeated by a sparse HEX (tiny record near 0 + CCFG at 0x57FD8).
    # Byte-count alone can be defeated by overlapping/repeated records at the same address.
    # Both checks together close both attack vectors.
    var span = self._check_max_addr - self._check_min_addr
    if span < 0x20000
      raise "value_error", format("firmware address span too small: 0x%06X-0x%06X (%i bytes span, expected >= 128KB)", self._check_min_addr, self._check_max_addr, span)
    end
    if self._check_bytes < 0x20000
      raise "value_error", format("firmware payload too small: %i bytes (expected >= 128KB)", self._check_bytes)
    end
    print("FLH: Verification of HEX file OK")
    # tasmota.log("FLH: Verification of HEX file OK", 2)
    self.file_checked = true
  end

end

return tubezb_cc2652_flasher()


#-
# Flash local firmware

import tubezb_cc2652_flasher as cc
cc.load("TubeZB_coord_firmware.hex")
cc.check()
cc.flash()

-#

#-
# Dump local firmware

import tubezb_cc2652_flasher as cc
cc.dump_to_file("TubeZB_dump.bin")

-#
