#!/usr/bin/env python3

import subprocess
import os
import shutil
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify
import os.path
app = Flask(__name__)

packagedDir= "/var/www/dash/"

class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@app.route("/")
def home():
    return "Imackager is running fine"

@app.route("/package", methods=["POST"])
def add_message():
    content = request.json
    resolutions = content["files"]["mainVideo"][0]["transcode"]
    videoFile = content["files"]["mainVideo"][0]["url"]
    dirName = str(content["assetId"]) +"/"
    outputDir = packagedDir + dirName
    if os.path.isdir(outputDir):
        shutil.rmtree(outputDir)
    os.mkdir(outputDir)
    videoBasename = os.path.splitext(os.path.basename(videoFile))[0]

    args = ["ffmpeg", "-y", "-i", videoFile, "-an", "-c:v",
			"libx264", "-bf", "0", "-crf", "22", "-x264opts", "keyint=50:min-keyint=50:no-scenecut", 
            outputDir + videoBasename + ".mp4"]
    ret = subprocess.call(args)
    if ret!= 0:
        raise InvalidUsage('Could not transcode the base video', status_code=400)

    for resolution in resolutions:
        print("Transcoding the resolution " + str(resolution))
        args = ["ffmpeg", "-y", "-i", videoFile, "-an",
            "-vf", "scale=-2:"+str(resolution), "-c:v",
			"libx264", "-bf", "0", "-crf", "22", "-x264opts", "keyint=50:min-keyint=50:no-scenecut", 
            outputDir + videoBasename
            + "_" + str(resolution) +"p.mp4"]
        ret = subprocess.call(args)
        if ret!= 0:
            raise InvalidUsage('Could not transcode the base video into smaller resolutions', status_code=400)
    mp4boxArgs = ["MP4Box", "-dash", "2000", "-profile", "live",  "-out", outputDir + "manifest.mpd"]
    videos = content["files"]["mainVideo"]
    audios = []
    if "audio" in content["files"]:
        audios = content["files"]["audio"]
    subtitles = []
    if "subtitle" in content["files"]:
        subtitles = content["files"]["subtitle"]
    signers = []
    if "signer" in content["files"]:
        signers = content["files"]["signer"]
    
    if len(signers)!=0:
        for signer in signers:
            signerFile = signer["url"] + "/index.xml"
            if not os.path.isfile(signerFile):
                raise InvalidUsage('The signer language file could not be fetched', status_code=400)

            signerTree=ET.parse(signerFile)
            signerRoot=signerTree.getroot()
            segments = signerRoot.find("Segments")
            for segment in segments:
                text = segment.find("Text").text
                if text is None:
                    text = ""
                videoFile = segment.find("Video").text
                tcin = segment.find("TCIN").text
                tcout = segment.find("TCOUT").text
                latitude = "0"
                longitude = "0"
                if "Latitude" in segment:
                    latitude = segment.find("Latitude").text
                if "Longitude" in segment:
                    longitude = segment.find("Longitude").text
                duration = segment.find("Duration").text

                print("Text=" + text + " Video=" + videoFile + " TCIN=" + tcin
                    + " TCOUT=" + tcout + " Latitude=" + latitude
                    + " Longitude=" + longitude + " Duration=" + duration)



    for video in videos:
        #if audio is muxed, only take the video from it
        mp4boxArgs = mp4boxArgs + [outputDir + videoBasename + ".mp4#video:role="+video["urn:mpeg:dash:role:2011"]]
        for resolution in resolutions:
            mp4boxArgs = mp4boxArgs + [outputDir + videoBasename + "_" + str(resolution) +"p.mp4"]
    for audio in audios:
        mp4boxArgs = mp4boxArgs + [audio["url"]+"#audio:role="+audio["urn:mpeg:dash:role:2011"]]
    
    print(mp4boxArgs)
    ret = subprocess.call(mp4boxArgs)
    if ret != 0:
        raise InvalidUsage('Could DASH the assets', status_code=400)
    tree=ET.parse(outputDir + "manifest.mpd")
    root=tree.getroot()
    
    for i, sub in enumerate(subtitles):
        for item in root.findall('{urn:mpeg:dash:schema:mpd:2011}Period'):
            AS = ET.Element("AdaptationSet")
            AS.set("contentType", "text")
            AS.set("mimeType","application/ttml+xml")
            AS.set("segmentAlignment", "true")
            AS.set("lang", sub["language"])
            role = ET.Element("Role")
            role.set("schemeIdUri", "urn:mpeg:dash:role:2011")
            role.set("value", "subtitle")
            AS.append(role)
            representation = ET.Element("Representation")
            representation.set("id", "xml_" + sub["language"] + "_" + str(i))
            representation.set("bandwidth", "1000")
            BaseURL = ET.Element("BaseURL")
            BaseURL.text = sub["url"]
            representation.append(BaseURL)
            AS.append(representation)
            item.append(AS)
    ET.register_namespace('', "urn:mpeg:dash:schema:mpd:2011")
    tree.write(outputDir + "manifest.mpd", xml_declaration=True)
    return "ok"
