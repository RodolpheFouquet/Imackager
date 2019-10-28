#!/usr/bin/env python3

import subprocess
from xml.dom import minidom
from xml.dom.minidom import Node
import os
import shutil
import xml.etree.ElementTree as ET
import urllib.request
from flask import Flask, request, jsonify, send_from_directory
import os.path
import random
import string
import json
from pprint import pprint
from shutil import copyfile
from threading import Thread

app = Flask(__name__)

#packagedDir= "/var/www/dash/"
packagedDir= "dash/"
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


@app.route('/dash/<path:path>')
def send_js(path):
    return send_from_directory('dash', path)

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@app.route("/")
def home():
    return "Imackager is running fine"


def download(workdir, url):
    if (url.startswith('http://')) or (url.startswith('https://')):
        print("Downloading " + url)
        basename = os.path.splitext(os.path.basename(url))[0]
        extension = os.path.splitext(os.path.basename(url))[1]

        urllib.request.urlretrieve (url.replace(" ", "%20"), workdir + basename +  extension)
        print(url + " downloaded")
        return workdir + basename + extension
    else:
        print("Copying " + url)
        basename = os.path.splitext(os.path.basename(url))[0]
        extension = os.path.splitext(os.path.basename(url))[1]

        copyfile(url, workdir + basename +  extension)
        print(url + " copied")
        return workdir + basename +  extension


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
        return "deu"
    if lang.startswith( 'es_' ):
        return "esp"
    else:
        return lang

def mapLang2(lang):
    if lang.startswith( 'ca_' ):
        return "ca"
    if lang.startswith( 'en_' ):
        return "en"
    if lang.startswith( 'de_' ):
        return "de"
    if lang.startswith( 'es_' ):
        return "es"
    else:
        return lang
def remove_blanks(node):
    for x in node.childNodes:
        if x.nodeType == Node.TEXT_NODE:
            if x.nodeValue:
                x.nodeValue = x.nodeValue.strip()
        elif x.nodeType == Node.ELEMENT_NODE:
            remove_blanks(x)

def tcToMilliseconds(timecode):
    comps = timecode.split(':')
    return int(comps[0])*3600000+ int(comps[1])*60000 + float(comps[2])*1000

def package(content):
    workdir = "/tmp/" + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10)) + "/"
    os.mkdir(workdir)
    print(content)
    resolutions = content["files"]["mainVideo"][0]["transcode"]
    videoFile = content["files"]["mainVideo"][0]["url"]

    if content["language"] == "de":
        content["language"] = "Deutsch"
    elif content["language"] == "fr":
        content["language"] = "Français"
    elif content["language"] == "ca":
        content["language"] = "Català"
    elif content["language"] == "es":
        content["language"] = "Español"
    else:
        content["language"] = "English"

    dirName = str(content["assetId"]) +"/"
    outputDir = packagedDir + dirName
    if os.path.isdir(outputDir):
        shutil.rmtree(outputDir)
    os.mkdir(outputDir)
    videoBasename = os.path.splitext(os.path.basename(videoFile))[0]

    videoFile = download(workdir, videoFile)

    args = ["ffmpeg", "-y", "-i", videoFile, "-an", "-c:v",
			"libx264", "-bf", "0", "-crf", "22", "-x264opts", "keyint=60:min-keyint=60:no-scenecut",
            outputDir + videoBasename + ".mp4"]
    ret = subprocess.call(args)
    if ret!= 0:
        shutil.rmtree(workdir)
        sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg": "Could not transcode the base video into smaller resolutions" } )

    for resolution in resolutions:
        print("Transcoding the resolution " + str(resolution))
        args = ["ffmpeg", "-y", "-i", videoFile, "-an",
            "-vf", "scale=-2:"+str(resolution), "-c:v",
			"libx264", "-bf", "0", "-crf", "22", "-x264opts", "keyint=60:min-keyint=60:no-scenecut",
            outputDir + videoBasename
            + "_" + str(resolution) +"p.mp4"]
        ret = subprocess.call(args)
        if ret!= 0:
            shutil.rmtree(workdir)
            sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Could not transcode the base video" } )

    mp4boxArgs = ["MP4Box", "-dash", "2000", "-profile", "live",  "-out", outputDir + "manifest.mpd"]
    videos = content["files"]["mainVideo"]
    audios = [ {'url': videoFile, 'urn:mpeg:dash:role:2011': 'main'}]
    if "audio" in content["files"]:
        audios = content["files"]["audio"]
    subtitles = []
    if "subtitle" in content["files"]:
        subtitles = content["files"]["subtitle"]
    signers = []
    if "signer" in content["files"]:
        signers = content["files"]["signer"]
    sls = []
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

        slVids = []

        for el in signerRoot.iter():
            if el.tag == "video":
                vid = download(workdir,  signer["url"] +  el.get("src"))
                slVids = slVids + [{"id" : el.get("{http://www.w3.org/XML/1998/namespace}id"), "begin": el.get("begin"), "end": el.get("end"), "file": vid}]
                #suppose we are at 600x600
        print(slVids)


        segments = []
        for el in signerRoot.findall(".//{http://www.w3.org/ns/ttml}body/{http://www.imac-project.eu}slSegments/{http://www.w3.org/ns/ttml}div/{http://www.w3.org/ns/ttml}p"):
            if el.tag == "{http://www.w3.org/ns/ttml}p":
                f = workdir +  el.get("{http://www.w3.org/XML/1998/namespace}id") + ".mp4"
                segments = segments + [{"id" : el.get("{http://www.w3.org/XML/1998/namespace}id"), "begin": el.get("begin"), "end": el.get("end"), "file": f}]
                # transcoding so we are frame accurate
        
        #TODO: trim if diff < threshold
        for i in range(len(segments)):
            args = ["ffmpeg", "-y", "-i", slVids[0]["file"], "-ss",  segments[i]["begin"], "-to", segments[i]["end"],  "-filter:v", 'crop=ih:ih,scale=300:300', "-bf", "0", "-crf", "22", "-c:v",
            "libx264", "-x264opts", "keyint=60:min-keyint=60:no-scenecut", "-an", segments[i]["file"]]
            ret = subprocess.call(args)
        blanks = []
        for i in range(len(segments)):
            if i < len(segments)-1:
                duration = (tcToMilliseconds(segments[i+1]["begin"]) - tcToMilliseconds(segments[i]["end"]))/1000.0
                blank = workdir + segments[i]["id"] + "_" + segments[i+1]["id"] + ".mp4"
                blanks = blanks + [blank]
                args = ["ffmpeg", "-t", str(duration), '-f', 'lavfi', '-i', 'color=c=black:s=300x300', '-c:v', 'libx264', '-tune', 'stillimage', '-pix_fmt', 'yuv420p', blank]
                ret = subprocess.call(args)

        playlist = "# playlist to concatenate"
        for i in range(len(segments)): 
            playlist = playlist+ "\n file '" + segments[i]["file"] +"'"
            if i < len(segments)-1:
                playlist = playlist + "\n file '" + blanks[i] +"'"

        with open(workdir + "/list.txt", "w") as f:
            f.write(playlist)
        outsl = workdir + "/sl"  + signer["language"] +".mp4"
        args = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", workdir + "/list.txt", "-bf", "0",  "-b:v", "500k", "-minrate", "500k", "-maxrate", "500k",  "-c:v","libx264", "-x264opts", "keyint=60:min-keyint=60:no-scenecut", "-an", outsl]
        ret = subprocess.call(args)
        sls = sls + [{"file": outsl, "role": signer["role"], "language": signer["language"]}]

    for video in videos:
        #if audio is muxed, only take the video from it
        mp4boxArgs = mp4boxArgs + [outputDir + videoBasename + ".mp4#video:role="+video["urn:mpeg:dash:role:2011"]]
        for resolution in resolutions:
            mp4boxArgs = mp4boxArgs + [outputDir + videoBasename + "_" + str(resolution) +"p.mp4"]
    for audio in audios:
        mp4boxArgs = mp4boxArgs + [audio["url"]+"#audio:role="+audio["urn:mpeg:dash:role:2011"]]

    # Fix once we have all SL segments
    for sl in sls:
        mp4boxArgs = mp4boxArgs + [ sl["file"] "#video:role="+ sl["role"]]
    if os.path.isfile(outputDir + videoBasename):
        print("Video exists")
    print(' '.join(mp4boxArgs))
    ret = subprocess.call(mp4boxArgs)
    if ret != 0:
        shutil.rmtree(workdir)
        sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Couldn't DASH the assets" } )

    tree=ET.parse(outputDir + "manifest.mpd")
    root=tree.getroot()

    for i, sub in enumerate(subtitles):
        subFile = download(outputDir, sub["url"])
        basename = os.path.splitext(os.path.basename(sub["url"]))[0]
        extension = os.path.splitext(os.path.basename(sub["url"]))[1]
        for item in root.findall('{urn:mpeg:dash:schema:mpd:2011}Period'):
            AS = ET.Element("AdaptationSet")
            AS.set("contentType", "text")
            AS.set("mimeType","application/ttml+xml")
            AS.set("segmentAlignment", "true")
            AS.set("lang", mapLang(sub["language"]))
            role = ET.Element("Role")
            role.set("schemeIdUri", "urn:mpeg:dash:role:2011")
            role.set("value", sub["urn:mpeg:dash:role:2011"])
            AS.append(role)
            representation = ET.Element("Representation")
            representation.set("id", "xml_" + mapLang(sub["language"]) + "_" + str(i))
            representation.set("bandwidth", "1000")
            BaseURL = ET.Element("BaseURL")
            BaseURL.text = basename + extension
            representation.append(BaseURL)
            AS.append(representation)
            item.append(AS)
    ET.register_namespace('', "urn:mpeg:dash:schema:mpd:2011")
    #tree.write(outputDir + "manifest.mpd", xml_declaration=True)
    with open(outputDir+ "manifest.mpd", "w") as xmlfile:
        x = minidom.parseString(ET.tostring(root))
        remove_blanks(x)
        x.normalize()
        xmlfile.write(x.toprettyxml(indent="  "))

    with open(jsonBDD) as f:
        data = json.load(f)
    subs = [dict()]
    for acc in content["acces"]["ST"]:
        for s in subtitles:
            if s["language"] == acc:
                base = os.path.splitext(os.path.basename(s["url"]))[0]
                ext = os.path.splitext(os.path.basename(s["url"]))[1]
                subs[0][acc]= "https://imac.gpac-licensing.com/dash/" + dirName +"/"+base+ext 

    for acc in content["acces"]["ST"]:
        for s in subtitles:
            if s["language"] == acc:
                base = os.path.splitext(os.path.basename(s["url"]))[0]
                ext = os.path.splitext(os.path.basename(s["url"]))[1]
                subs[0][acc]= "https://imac.gpac-licensing.com/dash/" + dirName +"/"+base+ext 



    data["contents"].append({
        "acces":content["acces"], "descriptionArray":content["descriptionArray"], "description":content["description"], 
        "name": str(len(data["contents"])+1) + ": " + content["programmeName"],
        "thumbnail": content["keyframe"],
        "url": "https://imac.gpac-licensing.com/dash/" + dirName + "manifest.mpd",
        "audioChannels" : 4,
        "subtitles": subs,
        "signer": [],
        "ad": [],
        "ast": []
    })


    with open(jsonBDD, 'w') as outfile:
        json.dump(data, outfile, indent=2)

    shutil.rmtree(workdir)
    sendResp(content["callbackUrl"], {"result":1, "assetId":content["assetId"], "language": content["language"], "msg":  "The content has been successfully packaged" } )

@app.route("/package", methods=["POST"])
def add_message():
    content = request.json
    process = Thread(target=package, args=[content])
    process.start()
    return "Packaging started"
