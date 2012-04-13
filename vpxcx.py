# generated by 'xml2py'
# flags 'vp8cx.xml -o vpxcx.py -l ../Release/vpxmt.dll -v'
from vpx import *
vpx_scaling_mode_1d = c_int # enum
VP8E_NORMAL = 0
VP8E_FOURFIVE = 1
VP8E_THREEFIVE = 2
VP8E_ONETWO = 3
VPX_SCALING_MODE = vpx_scaling_mode_1d
# ../vpxmt/include/vpx/vp8cx.h 203
class vpx_roi_map(Structure):
    pass
vpx_roi_map._fields_ = [
    # ../vpxmt/include/vpx/vp8cx.h 203
    ('roi_map', POINTER(c_ubyte)),
    ('rows', c_uint),
    ('cols', c_uint),
    ('delta_q', c_int * 4),
    ('delta_lf', c_int * 4),
    ('static_threshold', c_uint * 4),
]
assert sizeof(vpx_roi_map) == 60, sizeof(vpx_roi_map)
assert alignment(vpx_roi_map) == 4, alignment(vpx_roi_map)
vpx_roi_map_t = vpx_roi_map

# ../vpxmt/include/vpx/vp8cx.h 34
vpx_codec_vp8_cx = cdecl(POINTER(vpx_codec_iface_t), ) (('vpx_codec_vp8_cx', cdll.vpxmt,),)

int_fast8_t = c_byte

# ../vpxmt/include/vpx/vp8cx.h 232
class vpx_scaling_mode(Structure):
    pass
vpx_scaling_mode._fields_ = [
    # ../vpxmt/include/vpx/vp8cx.h 232
    ('h_scaling_mode', VPX_SCALING_MODE),
    ('v_scaling_mode', VPX_SCALING_MODE),
]
assert sizeof(vpx_scaling_mode) == 8, sizeof(vpx_scaling_mode)
assert alignment(vpx_scaling_mode) == 4, alignment(vpx_scaling_mode)
vpx_scaling_mode_t = vpx_scaling_mode
int_least16_t = c_short
uintptr_t = c_uint
intptr_t = c_int
size_t = c_uint

vp8e_token_partitions = c_int # enum
VP8_ONE_TOKENPARTITION = 0
VP8_TWO_TOKENPARTITION = 1
VP8_FOUR_TOKENPARTITION = 2
VP8_EIGHT_TOKENPARTITION = 3
# ../vpxmt/include/vpx/vp8cx.h 220
class vpx_active_map(Structure):
    pass
vpx_active_map_t = vpx_active_map
uintmax_t = c_ulonglong
vpx_active_map._fields_ = [
    # ../vpxmt/include/vpx/vp8cx.h 220
    ('active_map', POINTER(c_ubyte)),
    ('rows', c_uint),
    ('cols', c_uint),
]
assert sizeof(vpx_active_map) == 12, sizeof(vpx_active_map)
assert alignment(vpx_active_map) == 4, alignment(vpx_active_map)
vp8e_encoding_mode = c_int # enum
VP8_BEST_QUALITY_ENCODING = 0
VP8_GOOD_QUALITY_ENCODING = 1
VP8_REAL_TIME_ENCODING = 2

vp8e_enc_control_id = c_int # enum
VP8E_UPD_ENTROPY = 5
VP8E_UPD_REFERENCE = 6
VP8E_USE_REFERENCE = 7
VP8E_SET_ROI_MAP = 8
VP8E_SET_ACTIVEMAP = 9
VP8E_SET_SCALEMODE = 11
VP8E_SET_CPUUSED = 13
VP8E_SET_ENABLEAUTOALTREF = 14
VP8E_SET_NOISE_SENSITIVITY = 15
VP8E_SET_SHARPNESS = 16
VP8E_SET_STATIC_THRESHOLD = 17
VP8E_SET_TOKEN_PARTITIONS = 18
VP8E_GET_LAST_QUANTIZER = 19
VP8E_GET_LAST_QUANTIZER_64 = 20
VP8E_SET_ARNR_MAXFRAMES = 21
VP8E_SET_ARNR_STRENGTH = 22
VP8E_SET_ARNR_TYPE = 23
VP8E_SET_TUNING = 24
VP8E_SET_CQ_LEVEL = 25
VP8E_SET_MAX_INTRA_BITRATE_PCT = 26
int_least8_t = c_byte