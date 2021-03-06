#!/usr/bin/env python3

import subprocess
from xml.dom import minidom
from xml.dom.minidom import Node
import os
import shutil
import xml.etree.ElementTree as ET
import urllib.request
from flask import Flask, request, jsonify, send_from_directory
from urllib.parse import urlparse
import urllib.parse
import os.path
import random
import string
import json
from pprint import pprint
from shutil import copyfile
from threading import Thread
from itertools import groupby

app = Flask(__name__)


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

def escape(u):
        p = urlparse(u)
        r = p._replace(path=urllib.parse.quote(p.path))
        url = r.geturl()
        return url

def download(workdir, u, custom_extension = ""):
    if (u.startswith('http://')) or (u.startswith('https://')):
       # p = urlparse(u)
       # r = p._replace(path=urllib.parse.quote(p.path))
       # url = r.geturl()
        basename = os.path.splitext(os.path.basename(u))[0]
        extension = os.path.splitext(os.path.basename(u))[1]
        print("Downloading " + u+ " to " + workdir + basename + custom_extension+ extension)
	
        urllib.request.urlretrieve (u, workdir + basename + custom_extension+  extension)
        print(u + " downloaded")
        return workdir + basename +custom_extension+ extension
    else:
        url = u
        print("Copying " + url)
        basename = os.path.splitext(os.path.basename(url))[0]
        extension = os.path.splitext(os.path.basename(url))[1]

        copyfile(url, workdir + basename + custom_extension +extension)
        print(url + " copied")
        return workdir + basename + custom_extension + extension


@app.route("/test_callback", methods=["POST"])
def callback():
    content = request.json
    pprint(content)
    return "ok"


def removeDupicates(p):
    lines = []
    with open(p) as f:
        content = f.readlines()
        lines = [x[0] for x in groupby(content)]

    outF = open(p, "w")
    for line in lines:
        outF.write(line)
    outF.close()

def sendResp(url, resp):
    params = json.dumps(resp).encode('utf8')
    req = urllib.request.Request(url, data=params,
                             headers={'content-type': 'application/json'})
    response = urllib.request.urlopen(req)

def mapLang(lang):
    if lang.startswith( 'ca' ):
        return "cat"
    if lang.startswith( 'en' ):
        return "eng"
    if lang.startswith( 'de' ):
        return "deu"
    if lang.startswith( 'es' ):
        return "esp"
    else:
        return lang

def mapLangSL(lang):
    if lang.startswith( 'ca' ):
        return "csc"
    elif lang.startswith( 'en_US' ):
        return "ase"
    elif lang.startswith( 'en' ):
        return "bfi"
    elif lang.startswith( 'de' ):
        return "gsg"
    elif lang.startswith( 'es' ):
        return "ssp"
    else:
        return lang

def mapLang2(lang):
    if lang.startswith( 'ca' ):
        return "ca"
    if lang.startswith( 'en' ):
        return "en"
    if lang.startswith( 'de' ):
        return "de"
    if lang.startswith( 'es' ):
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
    packagedDir = content["publicationCdn"] + "/"
    jsonBDD = content["publicationFile"].replace("https://imac.gpac-licensing.com/", "/var/www/html/")
    resolutions = content["files"]["mainVideo"][0]["transcode"]
    videoFile = content["files"]["mainVideo"][0]["url"]
    originalLang =content["language"] 
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
    try:
        videoFile = download(workdir, videoFile)
    except Exception as err:
        print(err)
        sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Could not download " + videoFile } )
        return
    
    for resolution in resolutions:
        print("Transcoding the resolution " + str(resolution))
        args = ["ffmpeg", "-y", "-i", videoFile, "-an",
            "-vf", "scale=-2:"+str(resolution)+",fps=fps=30", "-c:v",
			"libx264", "-bf", "0", "-crf", "22", "-keyint_min", "60", "-g", "60", "-sc_threshold", "0","-write_tmcd", "0",
            outputDir + videoBasename
            + "_" + str(resolution) +"p.mp4"]
        ret = subprocess.call(args)
        if ret!= 0:
            shutil.rmtree(workdir)
            sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Could not transcode the base video" } )
            return
    mp4boxArgs = ["MP4Box", "-dash", "2000", "-profile", "live",  "-out", outputDir + "manifest.mpd"]

    audios = [ {'url': videoFile, 'urn:mpeg:dash:role:2011': 'main', 'language':  mapLang(originalLang)}]
    if "audio" in content["files"]:
        for a in content["files"]["audio"]:
                audios = audios + [a]
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
        try:
            signerFile = download(workdir, signerFile)
        except Exception:
            sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Could not download " + signerFile } )
            return

        if not os.path.isfile(signerFile):
            shutil.rmtree(workdir)
            sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "The SL couldn't be fetched" } )
            return
        signerTree=ET.parse(signerFile)
        signerRoot=signerTree.getroot()

        slVids = []

        for el in signerRoot.iter():
            if el.tag == "video":
                try:
                    vid = download(workdir,  signer["url"] + el.get("src"))
                except Exception:
                    sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Could not download " + signer["url"] +  el.get("src") } )
                    return
                slVids = slVids + [{"id" : el.get("{http://www.w3.org/XML/1998/namespace}id"), "begin": el.get("begin"), "end": el.get("end"), "file": vid}]
                #suppose we are at 600x600


        segments = []
        for el in signerRoot.findall(".//{http://www.w3.org/ns/ttml}body/{http://www.imac-project.eu}slSegments/{http://www.w3.org/ns/ttml}div/{http://www.w3.org/ns/ttml}p"):
            if el.tag == "{http://www.w3.org/ns/ttml}p":
                f = workdir +  el.get("{http://www.w3.org/XML/1998/namespace}id") + ".mp4"
                segments = segments + [{"id" : el.get("{http://www.w3.org/XML/1998/namespace}id"), "begin": el.get("begin"), "end": el.get("end"), "file": f}]
                # transcoding so we are frame accurate
        
        #TODO: trim if diff < threshold
        for i in range(len(segments)):
            print("cutting between " +segments[i]["begin"] + " and "+ segments[i]["end"])
            args = ["ffmpeg", "-y", "-i", slVids[0]["file"], "-ss",  segments[i]["begin"], "-to", segments[i]["end"],  "-filter:v", 'crop=ih:ih,scale=600:600,fps=fps=30', "-bf", "0", "-crf", "22", "-c:v",
            "libx264", "-keyint_min", "60", "-g", "60", "-sc_threshold", "0","-write_tmcd", "0", "-an", segments[i]["file"]]
            ret = subprocess.call(args)
        blanks = ["" for i in range(len(segments))]
        for i in range(len(segments)):
            if i < len(segments)-1:
                duration = (tcToMilliseconds(segments[i+1]["begin"]) - tcToMilliseconds(segments[i]["end"]))/1000.0
                if duration >0:
                    blank = workdir + segments[i]["id"] + "_" + segments[i+1]["id"] + ".mp4"
                    blanks[i] = blank
                    args = ["ffmpeg", "-t", str(duration), '-f', 'lavfi', '-i', 'color=c=black:s=600x600:rate=30', '-c:v', 'libx264', '-tune', 'stillimage', '-pix_fmt', 'yuv420p', blank]
                    ret = subprocess.call(args)

        playlist = "# playlist to concatenate"
        for i in range(len(segments)): 
            playlist = playlist+ "\n file '" + segments[i]["file"] +"'"
            if i < len(segments)-1 and  blanks[i] != "":
                playlist = playlist + "\n file '" + blanks[i] +"'"
        print("Encoding sign language stuff")
        print(playlist)
        with open(workdir + "/list.txt", "w") as f:
            f.write(playlist)
        outsl = workdir + "/sl"  + signer["language"] +".mp4"
        args = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", workdir + "/list.txt", "-bf", "0",  "-b:v", "500k", "-minrate", "500k", "-maxrate", "500k",  "-c:v","libx264", "-keyint_min", "60", "-g", "60", "-sc_threshold", "0","-write_tmcd", "0", "-an", outsl]
        ret = subprocess.call(args)
        sls = sls + [{"file": outsl, "role": signer["urn:mpeg:dash:role:2011"], "language": signer["language"]}]

    
    #if audio is muxed, only take the video from it
    mp4boxArgs = mp4boxArgs 
    for resolution in resolutions:
        mp4boxArgs = mp4boxArgs + [outputDir + videoBasename + "_" + str(resolution) +"p.mp4#video:role=main"]
    
    for audio in audios:
        try:
            f = download(outputDir, audio["url"], "-" + audio["language"])
        except Exception:
            sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Could not download " +  audio["url"]} )
            return
        if f.endswith(".aac"):
            arg = ["MP4Box", "-add", f, f.replace(".", "-")+".mp4"]
            subprocess.call(arg)
            # set the correct language
            arg = ["MP4Box", "-lang", mapLang(audio["language"]), f.replace(".", "-")+".mp4"]
            subprocess.call(arg)
            mp4boxArgs = mp4boxArgs + [ f+".mp4"+"#audio:role="+audio["urn:mpeg:dash:role:2011"]]
        elif  f.endswith(".mp4"):
            arg = ["MP4Box", "-lang", mapLang(audio["language"]), f]
            subprocess.call(arg)
            mp4boxArgs = mp4boxArgs + [f+"#audio:role="+audio["urn:mpeg:dash:role:2011"]]
        elif f.endswith(".ad"): #TODO extract & stuff
            continue
        else:
            mp4boxArgs = mp4boxArgs + [f+"#audio:role="+audio["urn:mpeg:dash:role:2011"]]


    if os.path.isfile(outputDir + videoBasename):
        print("Video exists")
    print(' '.join(mp4boxArgs))
    ret = subprocess.call(mp4boxArgs)
    if ret != 0:
        print("MP4Box failed")
        print(' '.join(mp4boxArgs))
        shutil.rmtree(workdir)
        sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Couldn't DASH the assets" } )
        return
        
    tree=ET.parse(outputDir + "manifest.mpd")
    root=tree.getroot()

    # Fix once we have all SL segments
    for sl in sls:
        sl["manifest"] = os.path.basename (sl["file"]).replace(".mp4", "") + ".mpd"
        mp4boxArgsSL = ["MP4Box", "-dash", "2000", "-profile", "live",  "-out", outputDir + sl["manifest"]]
        mp4boxArgsSL = mp4boxArgsSL + [ sl["file"] + "#video:role="+ sl["role"]]
        subprocess.call(mp4boxArgsSL)
        for item in root.findall('{urn:mpeg:dash:schema:mpd:2011}Period'):
            AS = ET.Element("AdaptationSet")
            AS.set("contentType", "video")
            AS.set("id","signerVideo_" +  mapLang(sl["language"]))
            AS.set("lang", "sgn-"+mapLangSL(sl["language"]))
            supp = ET.Element("SupplementalProperty")
            supp.set("schemeIdUri", "urn:imac:signer-metadata-adaptation-set-id:2019")
            supp.set("value","signerMetadata_" +  mapLang(sl["language"]))
            AS.append(supp)
            role = ET.Element("Role")
            role.set("schemeIdUri", "urn:mpeg:dash:role:2011")
            role.set("value", "sign") #until fixed in the ACM
            AS.append(role)
            representation = ET.Element("Representation")
            representation.set("id", "signer_600")
            BaseURL = ET.Element("BaseURL")
            BaseURL.text = sl["manifest"]
            representation.append(BaseURL)
            AS.append(representation)
            item.append(AS)
            print("Sign language added")

    for i, sub in enumerate(subtitles):
        try:
            subFile = download(outputDir, sub["url"])
        except Exception:
            sendResp(content["callbackUrl"], {"result":0, "assetId":content["assetId"], "language": content["language"], "msg":  "Could not download " +  sub["url"]} )
            return
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
            role.set("value", "subtitle") #until fixed in the ACM
            AS.append(role)
            representation = ET.Element("Representation")
            representation.set("id", "xml_" + mapLang(sub["language"]) + "_" + str(i))
            representation.set("bandwidth", "1000")
            BaseURL = ET.Element("BaseURL")
            BaseURL.text = basename + extension
            representation.append(BaseURL)
            AS.append(representation)
            item.append(AS)
            print("Subtitle added")

    hasAD=False
    ases = root.findall(".//{urn:mpeg:dash:schema:mpd:2011}Period/{urn:mpeg:dash:schema:mpd:2011}AdaptationSet")
    for AS in ases:
        if AS.find("{urn:mpeg:dash:schema:mpd:2011}Role").get("value") == "alternate":
            reps = AS.findall("{urn:mpeg:dash:schema:mpd:2011}Representation")
            for rep in reps:
                print(rep.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate").get("media"))
                for audio in content["files"]["audio"]:
                    if audio["containsAD"] == "1" and os.path.splitext(os.path.basename(audio["url"]))[0] in  rep.find("{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate").get("media"):
                        hasAD = True 
                        ad = ET.Element("AudioDescription")
                        ad.set("gain", audio["ADgain"])
                        if "classic" in os.path.splitext(os.path.basename(audio["url"]))[0]:
                            ad.set("mode", "classic")
                        elif "static" in os.path.splitext(os.path.basename(audio["url"]))[0]:
                            ad.set("mode", "static")
                        elif "dynamic" in os.path.splitext(os.path.basename(audio["url"]))[0]:
                            ad.set("mode", "dynamic")
                        break
                        rep.append(ad)
    ET.register_namespace('', "urn:mpeg:dash:schema:mpd:2011")
    if hasAD:
        ET.register_namespace('imac', "urn:imac:audio-description:2019")
    #tree.write(outputDir + "manifest.mpd", xml_declaration=True)
    print("Writing manifest")
    with open(outputDir+ "manifest.mpd", "wb") as xmlfile:
        mydata = ET.tostring(root)
        xmlfile.write(mydata)

    isDash2 = "dash2" in content["publicationCdn"]
    directory = "dash"
    if isDash2:
        directory = directory + "2"
    removeDupicates(outputDir+ "manifest.mpd")
    with open(jsonBDD) as f:
        data = json.load(f)
    subs = [dict()]
    if "ST" in content["acces"]:
        for acc in content["acces"]["ST"]:
            for s in subtitles:
                if s["language"] == acc:
                    base = os.path.splitext(os.path.basename(s["url"]))[0]
                    ext = os.path.splitext(os.path.basename(s["url"]))[1]
                    subs[0][acc]= "https://imac.gpac-licensing.com/" + directory + "/" + dirName +base+ext 
    slDic = [dict()]
    if "SL" in content["acces"]:
        for acc in content["acces"]["SL"]:
            for s in sls:
                if s["language"] == acc:
                    slDic[0][acc]= "https://imac.gpac-licensing.com/"+ directory+ "/" + dirName + s["manifest"]



    data["contents"].append({
        "acces":content["acces"], "descriptionArray":[content["descriptionArray"]],  
        "name": str(len(data["contents"])+1) + ": " + content["programmeName"],
        "thumbnail": content["keyframe"],
        "url": "https://imac.gpac-licensing.com"+ directory+"/" + dirName + "manifest.mpd",
        "audioChannels" : 4,
        "subtitles": subs,
        "signer": slDic,
        "poster": content["poster"],
        "ad": [],
        "ast": []
    })

    print("Writing json database")
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

