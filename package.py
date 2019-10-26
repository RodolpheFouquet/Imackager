#!/usr/bin/env python3

import subprocess
import os
import shutil
import xml.etree.ElementTree as ET
import urllib.request
from flask import Flask, request, jsonify
import os.path
import random
import string
import json
from pprint import pprint
from threading import Thread

resolutions = [ 1440, 1080, 720, 540, 480]

outputDir = "./Holy-dashed-E01-Dynamic-CAT/"
os.mkdir(outputDir)
workdir = "./tmp/"
mp4boxArgs = ["MP4Box", "-dash", "2000", "-profile", "live",  "-out", outputDir + "manifest.mpd"]
videoFile = "/home/tamareu/Holy/HolyLand_E01_CAT/Holy_Land-E01-CAT-AD-Dynamic_FOA.mp4"
videos = videoFile
videoBasename = os.path.splitext(os.path.basename(videoFile))[0]
args =["ffmpeg", "-y", "-loglevel", "info", "-i", videoFile, "-write_tmcd", "0","-c:v",
        "libx264", "-bf", "0", "-crf", "22", "-force_key_frames", "expr:gte(t,n_forced*2)",
        workdir + videoBasename + ".mp4"]
master_audio = workdir + videoBasename + ".mp4"
print("Transcoding main resolution")
ret = subprocess.call(args)

for resolution in resolutions:
    print("Transcoding the resolution " + str(resolution))
    args = ["ffmpeg", "-y",  "-loglevel", "info",  "-i", videoFile,  "-write_tmcd", "0", "-an",
        "-vf", "scale=-2:"+str(resolution), "-c:v",
	"libx264", "-bf", "0", "-crf", "22", "-force_key_frames", "expr:gte(t,n_forced*2)", 
        workdir + videoBasename
        + "_" + str(resolution) +"p.mp4"]
    ret = subprocess.call(args)
    if ret!= 0:
        print("Error while transcoding")

#if audio is muxed, only take the video from it
print("Adding video " + workdir + videoBasename)
mp4boxArgs = mp4boxArgs + [workdir + videoBasename + ".mp4#video:role=main"]
for resolution in resolutions:
    mp4boxArgs = mp4boxArgs + [workdir + videoBasename + "_" + str(resolution) +"p.mp4"]

mp4boxArgs = mp4boxArgs + [master_audio+"#audio"]
print(mp4boxArgs)
subprocess.call(mp4boxArgs +  ["-bs-switching", "no"])