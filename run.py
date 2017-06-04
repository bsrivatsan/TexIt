import sys, functools, glob, os, random, math, json
import numpy as np
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFilter
import argparse, io, httplib, urllib
import base64, requests, time
from werkzeug.exceptions import abort
from keys.settings import msft_pwd, math_pwd, math_id


# Internal  methods



# Code to detect text using Microsoft's cloud analytics platform. Taken from Microsoft API example docs
def detect_doc_msft(img):
    pwd = msft_pwd()
    headers = {
        # Request headers. Replace the key below with your subscription key.
        'Content-Type': 'application/json',
        'Ocp-Apim-Subscription-Key': pwd,
    }

    global_url = "http://www.texitapp.com/imgs/"
    img_path = global_url + img
    body = "{'url':'%s'}" %img_path
    print body

    # UNCOMMENT THIS FOR LOCAL TESTING
    # body = "{'url':'http://www.texitapp.com/imgs/1_1494808047.jpg'}"

    serviceUrl = 'westus.api.cognitive.microsoft.com'

    params = urllib.urlencode({'handwriting' : 'true'})
    output = ""
    status = False

    try:
        conn = httplib.HTTPSConnection(serviceUrl)
        conn.request("POST", "/vision/v1.0/RecognizeText?%s" % params, body, headers)
        response = conn.getresponse()

        # This is the URI where you can get the text recognition operation result.
        operationLocation = response.getheader('Operation-Location')
        print "Operation-Location:", operationLocation
        if operationLocation != None:
            status = True
            parsedLocation = operationLocation.split(serviceUrl)
            answerURL = parsedLocation[1]
            print "AnswerURL:", answerURL

            # Note: The response may not be immediately available. Handwriting recognition is an
            # async operation that can take a variable amount of time depending on the length
            # of the text you want to recognize. You may need to wait or retry this GET operation.

            time.sleep(10)
            conn = httplib.HTTPSConnection(serviceUrl)
            conn.request("GET", answerURL, '', headers)
            response = conn.getresponse()
            print response.status, response.reason
            output = json.loads(response.read())
            # print output FOR DEBUGGING
    except Exception as e:
        print e

    loc=[]
    doc = ""

    if status == True:
        result = output["recognitionResult"]["lines"]
        sort = sorted(result, key=lambda k: k['boundingBox'][1])
        # print sort FOR DEBUGGING
        for line in sort:
            doc = doc + line["text"] + "\n"
    else:
        return "ERROR: We were unable to process text from this image. Try a smaller, centered picture, with text written in clear, large, straight lines. Optimal image size isn't much larger than 3200x3200 pixels"
    #print(doc) FOR DEBUGGING
    return doc

# Detects math writing in an image using Mathpix API
def detect_math(img):
    image_uri = "data:image/jpg;base64," + base64.b64encode(open(img, "rb").read())
    math_key = math_pwd()
    math_id = math_id()
    r = requests.post("https://api.mathpix.com/v3/latex",
        data=json.dumps({'url': image_uri}),
        headers={"app_id": math_id, "app_key": math_key,
            "Content-type": "application/json"})
    returned = json.loads(r.text)

    # Handle errors
    if len(returned['error']) > 0:
        return "\n ERROR: We were unable to generate latex from these formulas. Try a smaller box, centered on the equations. Optimal equation conversion occurs for one equation at a time. \n"

    # Handle regular latex output
    latex = returned['latex']
    return "\n$$ " + latex + " $$\n"

# Code to transpose image to render 'right side up', added after odd rotation bug discovered
# Taken from: http://stackoverflow.com/questions/4228530/pil-thumbnail-is-rotating-my-image
def image_transpose_exif(im):
    exif_orientation_tag = 0x0112 # contains an integer, 1 through 8
    exif_transpose_sequences = [  # corresponding to the following
        [],
        [Image.FLIP_LEFT_RIGHT],
        [Image.ROTATE_180],
        [Image.FLIP_TOP_BOTTOM],
        [Image.FLIP_LEFT_RIGHT, Image.ROTATE_90],
        [Image.ROTATE_270],
        [Image.FLIP_TOP_BOTTOM, Image.ROTATE_90],
        [Image.ROTATE_90],
    ]

    try:
        seq = exif_transpose_sequences[im._getexif()[exif_orientation_tag] - 1]
    except Exception:
        return im
    else:
        return functools.reduce(lambda im, op: im.transpose(op), seq, im)

# Based on tutorial from http://stackoverflow.com/questions/273946/how-do-i-resize-an-image-using-pil-and-maintain-its-aspect-ratio
def image_resize(img):
    max_dim = 3150
    resize = min(max_dim/float(img.size[0]), max_dim/float(img.size[1]))
    if resize > 1:
        return img
    else:
        new_width = img.size[0] * resize
        new_height = img.size[1] * resize
        print("Resized to: ", new_width, new_height)
        img = img.resize((int(new_width), int(new_height)), Image.ANTIALIAS)
        return img

# Escapes special characters used in latex (to prevent latex compliation errors)
def sanitize_text(text):
    special_chars = ['&','%', '$', '#', '_', '{', '}', '~', '^']
    text = text.replace("\n", "\\\\\n")
    for char in special_chars:
        split_text = text.split(char)
        new_text = split_text[0]
        for i in range(1, len(split_text)):
            new_text = new_text + '\\' + char + split_text[i]
        text = new_text
    return text


# External Methods: Processing



# Code for image preprocessing
def process_image(img_filename):
    # Read image and convert to grey
    img = Image.open(img_filename)
    img = image_transpose_exif(img)
    img = image_resize(img)
    img = img.convert('L')

    # Sometimes, the following interferes with accurate text parsing. Other times, it helps.
    img = img.filter(ImageFilter.EDGE_ENHANCE)
    img.save(img_filename, optimize=True,quality=50)

# Code for cropping and converting math to latex
def box_latex(img_filename, x, y, w, h):
    try:
        img = Image.open(img_filename)
        int_x = float(x.strip())
        int_y = float(y.strip())
        int_w = float(w.strip())
        int_h = float(h.strip())
        crop_img = img.crop((int(int_x), int(int_y), int(int_x+int_w), int(int_y+int_h)))
        crop_img.save(img_filename, optimize=True,quality=75)
        text = detect_math(img_filename)
        img.save(img_filename, optimize=True,quality=75)
    except Exception:
        abort(500)

    return text

# Code for converting image to plaintext
def image_to_text(img_filename):
    #text = detect_doc_google(img)
    text = detect_doc_msft(img_filename)
    return text



# External Methods: Latex Conversion



# Code to convert plaintext to latex form
def convert_to_latex(plaintext, title, date, author):
    header = "\\documentclass{article} \n \\usepackage[utf8]{inputenc} \n \\title{%s} \n \\author{%s} \n \\date{%s} \n \\begin{document} \n \\maketitle" % (title, author, date)
    footer = '\end{document}'
    plaintext = plaintext.decode('utf-8')
    text = sanitize_text(plaintext)
    return header + '\n' + text + '\n' + footer

# Code to update latex with math-latex code
def update_latex(oldLatex, newLatex):
    old = oldLatex.split('\\maketitle')
    newText= newLatex.decode('utf-8')
    text = old[0] + '\\maketitle \n' + newText + old[1]
    return text

# Test bucket
if __name__ == '__main__':
    print("Fill body with testing code!")
    test_san = sanitize_text("Hi my name $is$$ '&','%', '$', '#', '_', '{', '}', '~', '^']Bharath!")
    print(test_san)