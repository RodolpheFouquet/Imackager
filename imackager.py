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

app = Flask(__name__)

packagedDir= "/home/tamareu/Bureau/opera/output"
jsonBDD= "./content.json"
#jsonBDD= "/var/www/html/playertest/content.json"

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


def download(workdir, url):
    print("Downloading " + url)
    basename = os.path.splitext(os.path.basename(url))[0]
    extension = os.path.splitext(os.path.basename(url))[1]

    urllib.request.urlretrieve (url, workdir + basename + "."+ extension)
    print(url + " downloaded")
    return workdir + basename + "."+ extension


@app.route("/test_callback", methods=["POST"])
def callback():
    content = request.json
    pprint(content)
    return "ok"

def sendResp(url, resp):
    params = json.dumps(resp).encode('utf8')
    req = urllib.request.Request(url, data=params,
                             headers={'content-type': 'application/json'})
    response = urllib.request.urlopen(req)

def mapLang(lang):
    if lang.startswith( 'ca_' ):
        return "cat"
    if lang.startswith( 'en_' ):
        return "eng"
    if lang.startswith( 'de_' ):
        return "ger"
    if lang.startswith( 'es_' ):
        return "esp"
    else:
        return lang

def package(content):
    workdir = "/tmp/" + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10)) + "/"
    os.mkdir(workdir)
    resolutions = content["files"]["mainVideo"][0]["transcode"]
    videoFile = content["files"]["mainVideo"][0]["url"]
    dirName = str(content["assetId"]) +"/"
    outputDir = packagedDir + dirName
    if os.path.isdir(outputDir):
        shutil.rmtree(outputDir)
    os.mkdir(outputDir)
    videoBasename = os.path.splitext(os.path.basename(videoFile))[0]
    
    videoFile = download(workdir, videoFile)

    args = ["ffmpeg", "-y", "-i", videoFile, "-an", "-c:v",
			"libx264", "-bf", "0", "-crf", "22", "-x264opts", "keyint=50:min-keyint=50:no-scenecut", 
            outputDir + videoBasename + ".mp4"]
    ret = subprocess.call(args)
    if ret!= 0: 
        shutil.rmtree(workdir)
        sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg": "Could not transcode the base video into smaller resolutions" } )

    for resolution in resolutions:
        print("Transcoding the resolution " + str(resolution))
        args = ["ffmpeg", "-y", "-i", videoFile, "-an",
            "-vf", "scale=-2:"+str(resolution), "-c:v",
			"libx264", "-bf", "0", "-crf", "22", "-x264opts", "keyint=50:min-keyint=50:no-scenecut", 
            outputDir + videoBasename
            + "_" + str(resolution) +"p.mp4"]
        ret = subprocess.call(args)
        if ret!= 0:
            shutil.rmtree(workdir)
            sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Could not transcode the base video" } )
            
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
    slTranscoded = ""
    slBasename = ""
    slBasenames = []
    if len(signers)!=0:
        for signer in signers:
            #for signer in signers:
            #Only use the first SL for now
            signerFile = signer["url"] + "/index.xml"
            
            signerFile = download(workdir, signerFile)
            if not os.path.isfile(signerFile):
                shutil.rmtree(workdir)
                sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "The SL couldn't be fetched" } )
                
            signerTree=ET.parse(signerFile)
            signerRoot=signerTree.getroot()
            segments = signerRoot.find("Segments")

            if len(segments)!=0:
            #Only use the first segment for now
            #for segment in segments:
                segment = segments[0]
                text = segment.find("Text").text
                if text is None:
                    text = ""
                videoFile = segment.find("Video").text
                videoFile = download(workdir, signer["url"] +"/" +  videoFile)

                basename = os.path.splitext(os.path.basename(videoFile))[0]
                extension = os.path.splitext(os.path.basename(videoFile))[1]
                print("Transcoding SL segment" + workdir)
                slBasename = basename + "."  + extension
                slTranscoded = outputDir + slBasename
                args = ["ffmpeg", "-y", "-i", videoFile, "-filter:v", 'crop=ih:ih', "-bf", "0", "-crf", "22", "-c:v",
                    "libx264", "-x264opts", "keyint=50:min-keyint=50:no-scenecut", "-an", slTranscoded]
                ret = subprocess.call(args)

                tcin = segment.find("TCIN").text
                tcout = segment.find("TCOUT").text
                latitude = "0"
                longitude = "0"
                if "Latitude" in segment:
                    latitude = segment.find("Latitude").text
                if "Longitude" in segment:
                    longitude = segment.find("Longitude").text
                duration = segment.find("Duration").text
                slBasenames = slBasenames + [slBasename]
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
    
    # Fix once we have all SL segments
    for sl in slBasenames:
        if sl != "":
            mp4boxArgs = mp4boxArgs + [ outputDir + slBasename + "#video:role=sign"]
    if os.path.isfile(outputDir + videoBasename):
        print("Video exists")
    print(mp4boxArgs)
    
    ret = subprocess.call(mp4boxArgs)
    if ret != 0:
        shutil.rmtree(workdir)
        sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Couldn't DASH the assets" } )
        
    tree=ET.parse(outputDir + "manifest.mpd")
    root=tree.getroot()
    
    for i, sub in enumerate(subtitles):
        for item in root.findall('{urn:mpeg:dash:schema:mpd:2011}Period'):
            AS = ET.Element("AdaptationSet")
            AS.set("contentType", "text")
            AS.set("mimeType","application/ttml+xml")
            AS.set("segmentAlignment", "true")
            AS.set("lang", mapLang(sub["language"]))
            role = ET.Element("Role")
            role.set("schemeIdUri", "urn:mpeg:dash:role:2011")
            role.set("value", "subtitle")
            AS.append(role)
            representation = ET.Element("Representation")
            representation.set("id", "xml_" + mapLang(sub["language"]) + "_" + str(i))
            representation.set("bandwidth", "1000")
            BaseURL = ET.Element("BaseURL")
            BaseURL.text = sub["url"]
            representation.append(BaseURL)
            AS.append(representation)
            item.append(AS)
    ET.register_namespace('', "urn:mpeg:dash:schema:mpd:2011")
    tree.write(outputDir + "manifest.mpd", xml_declaration=True)

    with open(jsonBDD) as f:
        data = json.load(f)

    data["contents"].append({
        "name": str(len(data["contents"])+1) + ": " + content["programmeName"],
        "thumbnail": content["keyframe"],
        "url": "https://imac.gpac-licensing.com/dash/" + dirName + "manifest.mpd",
        "audioChannels" : 4,
        "subtitles": [],
        "signer": [],
        "ad": [],
        "ast": []
    })


    with open(jsonBDD, 'w') as outfile:
        json.dump(data, outfile)
        
    shutil.rmtree(workdir)
    sendResp(content["callbackUrl"], {"result":1, "assetId":content["assetId"], "language": content["language"], "msg":  "The content has been successfully packaged" } )

@app.route("/package", methods=["POST"])
def add_message():
    content = request.json
    process = Thread(target=package, args=[content])
    process.start()
    return "Packaging started"
