#!/usr/bin/env python3

import subprocess
import os
import shutil
from flask import Flask, request, jsonify
app = Flask(__name__)

packagedDir= "packaged/"

@app.route("/")
def hello():
    return "Imackager is running fine"

@app.route("/package", methods=["POST"])
def add_message():
    content = request.json
    resolutions = content["files"]["mainVideo"][0]["transcode"]
    videoFile = content["files"]["mainVideo"][0]["url"]
    dirName = content["programmeName"] +"/"
    dirName = dirName.replace(" ", "_")
    outputDir = packagedDir + dirName
    if os.path.isdir(outputDir):
        shutil.rmtree(outputDir)
    os.mkdir(outputDir)
    for resolution in resolutions:
        print("Transcoding the resolution " + str(resolution))
        args = ["ffmpeg", "-y", "-i", videoFile, "-c:a", "aac",
            "-vf", "scale=-2:"+str(resolution), "-c:v",
			"libx264", "-bf", "0", "-crf", "22", outputDir + str(resolution) +"_" + videoFile]
        ret = subprocess.call(args)
        if ret!= 0:
            return "trancoding not ok"
    mp4boxArgs = ["MP4Box", "-dash", "2000", "-profile", "live",  "-out", outputDir + "manifest.mpd"]
    videos = content["files"]["mainVideo"]
    audios = content["files"]["audio"]
    subtitles = content["files"]["subtitle"]

    for video in videos:
        mp4boxArgs = mp4boxArgs + [video["url"]]
    for audio in audios:
        mp4boxArgs = mp4boxArgs + [audio["url"]]
    ret = subprocess.call(mp4boxArgs)
    if ret != 0:
        return "not ok"
    return "ok"
