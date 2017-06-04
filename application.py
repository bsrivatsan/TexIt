from __future__ import print_function
import os, sys, codecs, re, time, datetime
from flask import Flask, request, url_for, redirect, render_template, session, send_from_directory, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import abort
from flaskext.mysql import MySQL
import imghdr
from keys.settings import setup_sql
from run import image_to_text, convert_to_latex, process_image, box_latex, update_latex

application = Flask(__name__)
application = setup_sql(application)
mysql = MySQL()
mysql.init_app(application)

# Error Handling Endpoints

@application.errorhandler(400)
@application.errorhandler(404)
@application.errorhandler(405)
def page_not_found(e):
    """Not Found Error"""
    return render_template('400.html', errorcode = e.code), e.code

@application.errorhandler(500)
def server_error(e):
    """Internal Server Error"""
    return render_template('500.html'), e.code

# View Endpoints


@application.route('/')
def index():
    """splash/landing page"""
    if session.get('logged_in'):
        return redirect( url_for('files') ) 

    return render_template('index.html')

@application.route('/settings')
def settings():
    """settings page for creating/deleting courses, 
        and viewing user information"""

    if not session.get('logged_in'):
        return redirect(url_for('index'))

    # generate list of courses
    conn = mysql.get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT Classes.class_id, classname, color
        FROM Classes
        LEFT JOIN Users
        ON Users.user_id = Classes.user_id
        WHERE Users.user_id = (%s)
        GROUP BY Classes.color;
        ''', (session.get('user_id')) )
    ans = cur.fetchall()

    courses = []
    for row in ans:
        dct = {}
        dct['class_id'] = row[0]
        dct['name'] = row[1]
        dct['color'] = row[2]
        courses.append(dct)

    # fetch user information
    cur.execute('''
        SELECT firstname, lastname, email
        FROM Users
         WHERE user_id = (%s)
        ''', (session.get('user_id')) )
    name = cur.fetchone()
    usr = {}
    usr['first'] = name[0]
    usr['last'] = name[1]
    usr['email'] = name[2]

    return render_template('settings.html', courses=courses, user=usr)

@application.route('/files')
@application.route('/files/<string:class_id>')
def files(class_id=None):
    """display a table of the user's uploads; filter by class_id"""

    if not session.get('logged_in'):
        return render_template('index.html')

    conn = mysql.get_db()
    cur = conn.cursor()

    # generate list of all classes for the nav menu
    cur.execute('''
        SELECT Classes.class_id, classname, color
        FROM Classes
        LEFT JOIN Users
        ON Users.user_id = Classes.user_id
        WHERE Users.user_id = (%s)
        GROUP BY Classes.color;
        ''', session.get('user_id'))
    ans = cur.fetchall()

    course_name = ''
    courses = []
    for row in ans:
        dct = {}
        dct['class_id'] = row[0]
        dct['name'] = row[1]
        dct['color'] = row[2]
        courses.append(dct)

        # assign the course_name if 
        if class_id:
            if row[0] == int(class_id):
                course_name=row[1]

    # if not filtering by course return all uploads
    if class_id == None:
        cur.execute('''
            SELECT upload_id, title, upload_time, classname, color
            FROM Uploads
            LEFT JOIN Classes
            ON Uploads.class_id = Classes.class_id
            WHERE Uploads.user_id = (%s)
            ORDER BY Uploads.upload_id
            DESC;
            ''', session.get('user_id'))
        ans = cur.fetchall()
        course_name = "All Files"
    # return uploads, filtered by course
    else:
        # get uploads for the given course
        cur = conn.cursor()
        cur.execute('''
            SELECT upload_id, title, upload_time, classname, color
            FROM Uploads
            LEFT JOIN Classes
            ON Uploads.class_id = Classes.class_id
            WHERE Uploads.user_id = (%s)
            AND Classes.class_id = (%s)
            ORDER BY Uploads.upload_id
            DESC;
            ''', (session.get('user_id'), class_id))
        ans = cur.fetchall()

    uploads = []
    for row in ans:
        dct = {}
        dct['upload_id'] = row[0]
        dct['title'] = row[1]
        dct['date'] = row[2]
        dct['course'] = row[3]
        dct['color'] = row[4]
        uploads.append(dct)

    # Get the user's name to render the nav bar
    cur = conn.cursor()
    cur.execute('''SELECT firstname, lastname FROM Users WHERE user_id = (%s)''', 
        (session.get('user_id')) )
    name = cur.fetchone()
    render_name = name[0] + " " + name[1]

    return render_template('files.html', name=render_name, uploads=uploads, courses=courses, course_name=course_name)

@application.route('/details/<string:upload_id>')
def details(upload_id):
    """given an upload_id, retrieve the upload image & latex code for details.html, the latex editor"""

    if not session.get('logged_in'):
        return redirect(url_for('files'))

    conn = mysql.get_db()
    cur = conn.cursor()

    # get the upload info associated with the upload_id
    cur.execute(''' SELECT title, imagefile, latexfile FROM Uploads WHERE user_id = (%s) AND upload_id = (%s)
        ''', (session.get('user_id'), upload_id) )
    upload_record = cur.fetchone()

    # check if upload doesn't exist; this prevents a user from accessing another user's upload
    if not upload_record:
        abort(404)

    title = upload_record[0]
    img_filename = upload_record[1]
    latex_filename = upload_record[2]

    # extract the latex code from the latex file
    f=codecs.open('temp/'+latex_filename, 'r', "utf-8")
    latex_code=f.read()

    # render details.html
    data={"title":title, "code":latex_code, "image":"/get_upload/"+img_filename, "upload_id":upload_id, "image_url":img_filename, "latex_url":latex_filename}
    return render_template('details.html', file=data)


@application.route('/about')
def about():
    """static page including contact and app information"""
    return render_template('about.html')

# User Functions

@application.route('/signup', methods=['POST'])
def signup():
    """sign up a new user"""

    firstname = request.form['firstname']
    lastname = request.form['lastname']
    email = request.form['email']
    password = request.form['password']

    # form validation
    if not firstname or len(firstname) > 20:
        err_msg = {"header":"Invalid Sign Up", "main":"First name must be between 1 and 20 characters."}
        return render_template('error.html', error=err_msg)
    if not lastname or len(lastname) > 20:
        err_msg = {"header":"Invalid Sign Up", "main":"Last name must be between 1 and 20 characters."}
        return render_template('error.html', error=err_msg)  
    if not email or len(email) > 40 or not is_email_address_valid(email):
        err_msg = {"header":"Invalid Sign Up", "main":"Enter a valid email under 40 characters long."}
        return render_template('error.html', error=err_msg)        
    if not password or len(password) > 100:
        err_msg = {"header":"Invalid Sign Up", "main":"Enter a valid password under 100 characters."}
        return render_template('error.html', error=err_msg)          

    conn = mysql.get_db()
    cur = conn.cursor()

    # check if account exists associated with the email
    cur.execute('''SELECT * FROM Users WHERE email = (%s);''', email)
    account_found = cur.fetchone()

    # if email not taken, make new account and sign in
    if not account_found:
        cur.execute('''INSERT INTO Users (firstname, lastname, email, password) VALUES (%s, %s, %s, %s);
            ''', (firstname, lastname, email, generate_password_hash(password)) )
        conn.commit()

        # get user_id
        cur.execute('''SELECT user_id FROM Users WHERE email=(%s);''', (email) )
        user_id = cur.fetchone()[0]

        # start session
        session['logged_in'] = True
        session['user_id'] = user_id

        # add default course and color into table
        cur.execute('''INSERT INTO Classes (user_id, classname, color) VALUES (%s, 'Default Class', 'Grey'); 
            ''', (user_id) )
        conn.commit()

        return redirect(url_for('files'))
    # else, notify user that email is already taken
    else:
        return render_template('index.html', error='This email has already been registered!')

@application.route('/login', methods=['POST'])
def login():
    """login the user into his/her account"""

    email = request.form['email']
    password = request.form['password']
    
    if not email or len(email) > 40 or not is_email_address_valid(email):
        err_msg = "Invalid email."
        return render_template('index.html', error=err_msg)

    if not password or len(password) > 100:
        err_msg = "Invalid password."
        return render_template('index.html', error=err_msg)

    conn = mysql.get_db()
    cur = conn.cursor()

    # check if account exists
    cur.execute('''SELECT user_id, password FROM Users WHERE email = (%s)''', (email))
    ans = cur.fetchone()
    if not ans:
        error_msg = "There is no account for this email."
        return render_template('index.html', error=error_msg)   

    hashed_password = ans[1]
    if check_password_hash(hashed_password, password):
        session['logged_in'] = True
        session['user_id'] = ans[0]
        return redirect(url_for('files'))
    else:
        error_msg = "Invalid email or password."
        return render_template('index.html', error=error_msg)

@application.route('/logout')
def logout():
    session['logged_in'] = False
    return redirect(url_for('index'))

# API Functions

@application.route('/new_course', methods=['POST'])
def new_course():
    """create a new course; store in name and color in the database"""

    if not session.get('logged_in'):
        return redirect(url_for('index'))

    name = request.form['name']
    color = request.form['color']

    # form validation

    if not name or len(name) > 20:
        err_msg = {"header":"Error Creating Course!", "main":"Enter a valid course name under 20 characters."}
        return render_template('error.html', error=err_msg)
    if not color or len(color) > 20:
        err_msg = {"header":"Error Creating Course!", "main":"You must select a valid color."}
        return render_template('error.html', error=err_msg)

    conn = mysql.get_db()
    cur = conn.cursor()

    # insert new course into database
    cur.execute('''INSERT INTO Classes (user_id, classname, color) VALUES (%s, %s, %s);
        ''', (session.get('user_id'), name, color))
    conn.commit()
    return redirect(url_for('settings'))

@application.route('/get_upload/<path:filename>')
def get_upload(filename):
    """serve up latex and uploaded image files from the server's file repository"""

    if not session.get('logged_in'):
        return redirect(url_for('files'))

    # validate the session's user_id against the user_id associated with the filename
    filename_parts = filename.split('_')
    if filename_parts[0] == 'latex': # latex filename
        if int(filename_parts[1]) != session.get('user_id'):
            abort(404)
    else: # img filename
        if int(filename_parts[0]) != session.get('user_id'):
            abort(404)
    
    return send_from_directory(application.config['UPLOAD_FOLDER'], filename)

@application.route('/new', methods=['POST'])
def newfile():
    """create a new upload: parse text from uploaded image and generate latex"""

    if not session.get('logged_in'):
        return redirect(url_for('files')) 

    file = request.files['upload_pic']
    course_id = request.form['course']
    title = request.form['title']

    # form validation
    ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])
    filetype = str(file.filename.split('.')[-1])
    filetype = filetype.lower()

    if not file:
        err_msg = {"header":"Error Uploading File!", "main":"You must select a file to upload."}
        return render_template('error.html', error=err_msg)
    if filetype not in ALLOWED_EXTENSIONS:
        err_msg = {"header":"Bad Filetype", "main":"Currently, TexIt only supports .png, .jpg, and .jpeg files!"}
        return render_template('error.html', error=err_msg)
    if not course_id or len(course_id) > 6:
        err_msg = {"header":"Error Uploading File!", "main":"Enter a valid course."}
        return render_template('error.html', error=err_msg)
    if not title or len(title) > 40:
        err_msg = {"header":"Error Uploading File!", "main":"Enter a valid title under 40 characters."}
        return render_template('error.html', error=err_msg)

    conn = mysql.get_db()
    cur = conn.cursor()

    # generate timestamp
    timestamp = str(int(time.time()))
    timestamp = timestamp.encode('utf-8')
    formatted_time = datetime.datetime.fromtimestamp(int(time.time()) ).strftime('%Y-%m-%d %H:%M:%S')
    latex_time = datetime.datetime.fromtimestamp(int(time.time()) ).strftime('%m/%d/%Y')

    # save image locally on server
    filename = str(session.get('user_id'))+ '_' + timestamp
    filename = filename.encode('utf-8')
    img_filename = filename + '.jpg' # internally covert all files to jpg to reduce file size
    img_save_path = os.path.join(application.config['UPLOAD_FOLDER'], img_filename)
    file.save(img_save_path)
    print(img_filename)

    real_filetype = imghdr.what(img_save_path)
    if real_filetype not in ALLOWED_EXTENSIONS:
        type_error_msg = {"header":"Bad Filetype", "main":"Currently, TexIt only supports .png, .jpg, and .jpeg files!"}
        return render_template('error.html', error=type_error_msg)

    # process image
    process_image(img_save_path)
    size = float(os.stat(img_save_path).st_size) / 1000000
    if (size > 4):
        size_error_msg = {"header":"File Too Large", "main":"Unfortunately, your file is too large to be parsed by our partner APIs. Please retry with a smaller file - we recommend files under 6mb."}
        return render_template('error.html', error=type_error_msg)

    # fetch name of the user for latex template
    cur.execute('''SELECT firstname, lastname FROM Users WHERE user_id = (%s) 
        ''', (session.get('user_id')) )
    name = cur.fetchone()
    latex_name = name[0] + " " + name[1]

    # generate latex
    text = image_to_text(img_filename)
    latex = convert_to_latex(text, title, latex_time, latex_name)
    latex = latex.encode('utf-8')

    # save latex in txt file
    latex_filename ='latex_' + filename
    latex_save_path = os.path.join(application.config['UPLOAD_FOLDER'], latex_filename)
    with open(latex_save_path, "w") as f:
        f.write("{}".format(latex))

    # add new entry to Upload table
    cur = conn.cursor()
    cur.execute('''INSERT INTO Uploads (user_id, title, imagefile, latexfile, upload_time, last_mod_time, class_id) 
        VALUES (%s, %s, %s, %s, %s, %s, %s);
        ''', (session.get('user_id'), title, img_filename, latex_filename, formatted_time, formatted_time, course_id) )
    conn.commit()

    # get upload ID
    cur = conn.cursor()
    cur.execute('''
        SELECT upload_id FROM Uploads WHERE user_id=(%s) AND upload_time=(%s);
        ''', (session.get('user_id'), formatted_time) )
    upload_id = cur.fetchone()[0]

    return redirect( url_for('details', upload_id=upload_id) )

@application.route("/box_upload/", methods=["POST"])
def box_upload():
    """generate latex equations from coodinates of a selected box region of an upload image"""
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    upload_id = request.form['upload_id']
    x = request.form['x']
    y = request.form['y']
    w = request.form['w']
    h = request.form['h']
    latex_url = request.form['latex_url']
    image_url = request.form['image_url']

    if not x or not y or not w or not h or not latex_url or not image_url:
        return redirect( url_for('details', upload_id=upload_id) )
    if x == None or y == None or w == None or h == None or latex_url == None or image_url == None:
        return redirect( url_for('details', upload_id=upload_id) )

    latex_save_path = os.path.join(application.config['UPLOAD_FOLDER'], latex_url)
    image_save_path = os.path.join(application.config['UPLOAD_FOLDER'], image_url)

    with open(latex_save_path, "rb") as f:
        origLatex = f.read()

    newLatex = box_latex(image_save_path, x, y, w, h)
    latex = update_latex(origLatex, newLatex)
    with open(latex_save_path, "w") as f:
        f.write("{}".format(latex))

    return redirect( url_for('details', upload_id=upload_id) )
   
@application.route('/delete_upload/<string:upload_id>')
def delete_upload(upload_id):
    """delete an upload with upload_id, including the database entry, image file and latex file"""
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    conn = mysql.get_db()
    cur = conn.cursor()

    # get filenames for all pictures and latex files associated with the upload
    cur.execute('''SELECT imagefile, latexfile FROM Uploads WHERE user_id = (%s) AND upload_id = (%s);
        ''', (session.get('user_id'), upload_id))
    uploads_to_delete = cur.fetchall()

    if not uploads_to_delete:
        abort(404)

    for imagefile, latexfile in uploads_to_delete:
        os.system("rm temp/" + imagefile)
        os.system("rm temp/" + latexfile)

    # delete the class from the Classes and Uploads table in the backend
    cur.execute('''DELETE FROM Uploads WHERE user_id = (%s) AND upload_id = (%s);
        ''', (session.get('user_id'), upload_id) )
    conn.commit()

    return redirect( url_for('files') )

@application.route('/delete_course/<string:course_id>')
def delete_course(course_id):
    """delete a course, along with the coorespoding uploads"""

    if not session.get('logged_in'):
        return redirect(url_for('index'))

    conn = mysql.get_db()
    cur = conn.cursor()

    # delete all pictures and latex files associated with the course
    cur.execute('''
        SELECT imagefile, latexfile FROM Uploads WHERE user_id = (%s) AND class_id = (%s);
        ''', (session.get('user_id'), course_id))
    uploads_to_delete = cur.fetchall()      

    for imagefile, latexfile in uploads_to_delete:
        os.system("rm temp/" + imagefile)
        os.system("rm temp/" + latexfile)

    # delete the course from the Classes and Uploads table in the backend
    cur.execute('''
        DELETE FROM Classes WHERE user_id = (%s) AND class_id = (%s);
        DELETE FROM Uploads WHERE user_id = (%s) AND class_id = (%s);
        ''', (session.get('user_id'), course_id, session.get('user_id'), course_id))
    conn.commit()
    
    return redirect( url_for('settings') )

@application.route("/imgs/<path:path>")
def images(path):
    """fetch images of uploads"""
    img_filename = path
    img_save_path = os.path.join(application.config['UPLOAD_FOLDER'], img_filename)
    resp = make_response(open(img_save_path).read())
    resp.content_type = "image/jpeg"
    return resp

@application.route("/save/<string:latex_url>", methods=['POST'])
def save(latex_url):
    """Save latex input"""
    latex = request.form['data']
    latex_split = [e+'\\documentclass' for e in latex.split('\\documentclass') if e]
    latex = '\\documentclass' + ''.join(latex_split[1:])
    latex = latex.encode('utf-8')
    upload_id = request.form['upload_id']

    latex_filename = latex_url
    latex_save_path = os.path.join(application.config['UPLOAD_FOLDER'], latex_filename)
    with open(latex_save_path, "w") as f:
        f.write("{}".format(latex))
    return redirect( url_for('details', upload_id=upload_id) )

# Utility Methods

def is_email_address_valid(email):
    """Validate the email address using a regex."""
    if not re.match("^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$", email):
        return False
    return True

if __name__ == "__main__":
    application.run()