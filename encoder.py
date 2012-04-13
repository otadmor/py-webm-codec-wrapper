from ctypes import windll, Structure, byref, pointer, cast, c_char_p, POINTER, create_string_buffer, c_ubyte, string_at, c_void_p, c_size_t, cdll
import os
import vpx as vpxmt
from vpxcx import vpx_codec_vp8_cx
from vpx_encoder import vpx_codec_enc_config_default, LP_vpx_codec_enc_cfg_t, vpx_codec_enc_init, vpx_codec_encode, VPX_DL_REALTIME, vpx_codec_get_cx_data, LP_vpx_codec_iter_t, vpx_codec_iter_t, VPX_CODEC_CX_FRAME_PKT, VPX_FRAME_IS_KEY
import struct
libc = cdll.msvcrt
#define VPX_CODEC_DISABLE_COMPAT 1
#include "vpx/vpx_encoder.h"
#include "vpx/vp8cx.h"
#define interface (vpx_codec_vp8_cx())
fourcc = 0x30385056

IVF_FILE_HDR_SZ = (32)
IVF_FRAME_HDR_SZ = (12)

def die(str):
    raise Exception(str)
    
def read_frame(f, img):
    
    res = True

    to_read = img.contents.w*img.contents.h*3/2
    d = f.read(to_read)
    if(len(d) != to_read):
        res = False
        if(len(d) > 0):
            print ("Warning: Read partial frame. Check your width & height!\n")
    libc.memcpy(cast(img.contents.planes[0], c_void_p), cast(create_string_buffer(d), c_void_p), c_size_t(len(d)))
    return res
       
def write_ivf_file_header(outfile, cfg, frame_cnt):
    if (cfg.g_pass != vpxmt.VPX_RC_ONE_PASS and cfg.g_pass != vpxmt.VPX_RC_LAST_PASS):
        return
    header = struct.pack("<4sHHIHHIIII", 
        'DKIF', 
        0, 
        IVF_FILE_HDR_SZ, 
        fourcc, 
        cfg.g_w,
        cfg.g_h,
        cfg.g_timebase.den,
        cfg.g_timebase.num,
        frame_cnt,
        0)
    assert len(header) == IVF_FILE_HDR_SZ
    outfile.write(header)
    
    
def write_ivf_frame_header(outfile, pkt):
    
    if(pkt.kind != VPX_CODEC_CX_FRAME_PKT):
        return
    pts = pkt.data.frame.pts
    
    header = struct.pack("<III", 
        pkt.data.frame.sz,
        pts&0xFFFFFFFF,
        pts >> 32)
    assert len(header) == IVF_FRAME_HDR_SZ
    outfile.write(header)
    
def die_codec(ctx, s):
    byref_ctx = byref(ctx)
    detail = cast(vpxmt.vpx_codec_error_detail(byref_ctx), c_char_p).value

    s = ("%s: %s\n" % (s, cast(vpxmt.vpx_codec_error(byref_ctx), c_char_p).value,))
    if(detail != None):
        s += ("    %s\n" % (detail,))
    raise Exception(s)


def encoder_main(width, height, infile_name, outfile_name):
    width = int(width)
    height = int(height)
    
    cfg = vpxmt.vpx_codec_enc_cfg()
    if width < 16 or width % 2 != 0 or height < 16 or height % 2 != 0:
        die("Invalid resolution: %ldx%ld" % (width, height,))
    
    raw = vpxmt.vpx_img_alloc(None, vpxmt.VPX_IMG_FMT_I420, width, height, 1)
    if raw is None:
        die("Faile to allocate image" % (width, height,))
    try:
        outfile = open(outfile_name, "wb")
    except:
        die("Failed to open %s for writing" % (outfile_name,))
    raw_ptr = cast(raw, vpxmt.LP_vpx_image_t)
    print ("Using %s\n" % (cast(vpxmt.vpx_codec_iface_name(vpx_codec_vp8_cx()), c_char_p).value,))
    
    cfg_ptr = cast(pointer(cfg), LP_vpx_codec_enc_cfg_t)
    
    #/* Populate encoder configuration */                                      //
    res = vpx_codec_enc_config_default(vpx_codec_vp8_cx(), cfg_ptr, 0); 
    if(res != 0):
        print ("Failed to get config: %s\n" % (vpxmt.vpx_codec_err_to_string(res),))
        return EXIT_FAILURE
        
    cfg.rc_target_bitrate = width * height * cfg.rc_target_bitrate / cfg.g_w / cfg.g_h;                              
    cfg.g_w = width
    cfg.g_h = height

    write_ivf_file_header(outfile, cfg, 0)
    
    try:
        # /* Open input file for this encoding pass */
        infile = open(infile_name, "rb")
    except:
        die("Failed to open %s for reading" % (infile_name,))
        
    #/* Initialize codec */
    codec = vpxmt.vpx_codec_ctx()
    codec_ptr = cast(pointer(codec), vpxmt.LP_vpx_codec_ctx_t)
    if(vpx_codec_enc_init(codec_ptr, vpx_codec_vp8_cx(), cfg_ptr, 0)):
        die_codec(codec, "Failed to initialize encoder")

    frame_avail = 1
    got_data = 0
    frame_cnt = 0
    flags = 0
    key_frames = 0
    
    while (frame_avail or got_data):
        iter_data = vpx_codec_iter_t()
        iter_data_ptr = pointer(iter_data)
        
        frame_avail = read_frame(infile, raw_ptr)
        encoded = vpx_codec_encode(codec_ptr, raw_ptr if frame_avail else None, frame_cnt, 1, flags, VPX_DL_REALTIME)
        if(encoded != 0):
            die_codec(codec, "Failed to encode frame")
        got_data = False
        
        pkt_ptr = vpx_codec_get_cx_data(codec_ptr, iter_data_ptr)
        
        while( bool(pkt_ptr) ):
            pkt = pkt_ptr.contents
            
            got_data = True
            #import pdb; pdb.set_trace()
            if pkt.kind == VPX_CODEC_CX_FRAME_PKT:
                write_ivf_frame_header(outfile, pkt)
                outfile.write(string_at(pkt.data.frame.buf, pkt.data.frame.sz))
            else:
                print "not written"
            if pkt.kind == VPX_CODEC_CX_FRAME_PKT and (pkt.data.frame.flags & VPX_FRAME_IS_KEY) != 0:
                key_frames += 1
                #print "K",
            else :
                #print ".",
                pass
            outfile.flush()
            #
            pkt_ptr = vpx_codec_get_cx_data(codec_ptr, iter_data_ptr)
        #if frame_cnt % 10 == 0 : print "10",
        frame_cnt += 1
    print "end"
    infile.close()
    
    print ("Processed %d frames.\n" % (frame_cnt-1,))
    print ("Processed %d key frames.\n" % (key_frames,))
    if(vpxmt.vpx_codec_destroy(codec_ptr)):
        die_codec(codec, "Failed to destroy codec")
        
    #/* Try to rewrite the file header with the actual frame count */
    try:
        outfile.seek(0, os.SEEK_SET)
    #if(!fseek)
        write_ivf_file_header(outfile, cfg, frame_cnt-1)
    except:
        pass
        
    outfile.close()
    
    return 0
        
        
if __name__ == "__main__":
    import sys
    encoder_main(*sys.argv[1:])