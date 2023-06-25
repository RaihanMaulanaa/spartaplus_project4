import os
from os.path import join, dirname
from dotenv import load_dotenv
from pymongo import MongoClient
import jwt
from datetime import datetime, timedelta
import hashlib
from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    redirect,
    url_for
)
from werkzeug.utils import secure_filename

app = Flask(__name__)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

# konfigurasi ini berguna saat mengupdate data template server akan reload secara otomatis
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['UPLOAD_FOLDER'] = './static/profile_pics'

SECRET_KEY = 'SPARTA'

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

TOKEN_KEY = 'mytoken'


@app.route('/', methods=['GET'])
def home():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )
        user_info = db.users.find_one({'username': payload.get('id')})
        return render_template('index.html', user_info=user_info)
    except jwt.ExpiredSignatureError:
        msg = 'Token anda telah kadaluwarsa'
        return redirect(url_for('login', msg=msg))
    except jwt.exceptions.DecodeError:
        msg = 'Sepertinya ada kesalahan'
        return redirect(url_for('login', msg=msg))


@app.route('/login', methods=['GET'])
def login():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )
        user_info = db.users.find_one({'username': payload.get('id')})
        return redirect(url_for('home', user_info=user_info))
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        msg = request.args.get('msg')
        return render_template('login.html', msg=msg)


@app.route('/user/<username>', methods=['GET'])
def user(username):
    # endpoint untuk mengambil informasi profil user
    # dan seluruh post mereka
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )
        status = username == payload["id"]
        user_info = db.users.find_one(
            {"username": username},
            {"_id": False}
        )
        return render_template(
            "user.html",
            user_info=user_info,
            status=status
        )
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))


@app.route('/sign_in', methods=['POST'])
def sign_in():
    username_receive = request.form['username_give']
    password_receive = request.form['password_give']
    pw_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    result = db.users.find_one({
        'username': username_receive,
        'password': pw_hash
    })
    if result:
        payload = {
            'id': username_receive,
            # the token will be valid for 24 hours
            "exp": datetime.utcnow() + timedelta(seconds=60 * 60 * 24),  # * 60 * 1
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return jsonify({'result': 'success', 'token': token})
        # Mari tangani kasus dimana kombinasi id dan
        # password tidak dapat ditemukan
    else:
        return jsonify({
            "result": "fail",
            "msg": "We could not find a user with that id/password combination",
        })


@app.route('/sign_up/save', methods=['POST'])
def sign_up():
    username_receive = request.form.get('username_give')
    password_receive = request.form.get('password_give')
    password_hash = hashlib.sha256(
        password_receive.encode('utf-8')).hexdigest()
    doc = {
        "username": username_receive,                               # id
        "password": password_hash,                                  # password
        # user's name is set to their id by default
        "profile_name": username_receive,
        # profile image file name
        "profile_pic": "",
        # a default profile image
        "profile_pic_real": "profile_pics/profil.png",
        # a profile description
        "profile_info": ""
    }
    db.users.insert_one(doc)
    return jsonify({'result': 'success'})


@app.route('/sign_up/check_dup', methods=['POST'])
def check_dup():
    username_receive = request.form['username_give']
    exists = bool(db.users.find_one({'username': username_receive}))
    return jsonify({'result': 'success', 'exists': exists})


@app.route('/update_profile', methods=['POST'])
def update_profile():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )
        username = payload.get('id')

        name_receive = request.form.get('name_give')
        about_receive = request.form.get('about_give')

        new_doc = {
            'profile_name': name_receive,
            'profile_info': about_receive,
        }

        if "file_give" in request.files:
            file = request.files["file_give"]
            filename = secure_filename(file.filename)
            extension = filename.split(".")[-1]
            file_path = f"profile_pics/{username}.{extension}"
            file.save("./static/" + file_path)
            new_doc["profile_pic"] = filename
            new_doc["profile_pic_real"] = file_path
        db.users.update_one(
            {'username': username},
            {'$set': new_doc}
        )

        return jsonify({
            'result': 'success',
            'msg': 'Profil anda telah diperbarui'
        })
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))


@app.route('/posting', methods=['POST'])
def posting():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )
        user_info = db.users.find_one({'username': payload.get('id')})
        comment_receive = request.form.get('comment_give')
        date_receive = request.form.get('date_give')
        doc = {
            'username': user_info.get('username'),
            'profile_name': user_info.get('profile_name'),
            'profile_pic_real': user_info.get('profile_pic_real'),
            'comment': comment_receive,
            'date': date_receive,
        }
        db.posts.insert_one(doc)
        return jsonify({
            'result': 'success',
            'msg': 'Posting berhasil!'
        })
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))


@app.route('/get_posts', methods=['GET'])
def get_posts():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )
        username_receive = request.args.get('username_give')

        if username_receive == '':
            posts = list(db.posts.find({}).sort('date', -1).limit(20))
        else:
            posts = list(db.posts.find(
                {'username': username_receive}).sort('date', -1).limit(20))

        # menampilkan list 20 post terakhir
        for post in posts:
            post['_id'] = str(post['_id'])
            # ---
            post['count_heart'] = db.likes.count_documents({
                'post_id': post['_id'],
                'type': 'heart',
            })
            post['heart_by_me'] = bool(db.likes.find_one({
                'post_id': post['_id'],
                'type': 'heart',
                'username': payload["id"]
            }))
            # ---
            post['count_star'] = db.likes.count_documents({
                'post_id': post['_id'],
                'type': 'star',
            })
            post['star_by_me'] = bool(db.likes.find_one({
                'post_id': post['_id'],
                'type': 'star',
                'username': payload["id"]
            }))
            # ---
            post['count_thumbs'] = db.likes.count_documents({
                'post_id': post['_id'],
                'type': 'thumbs',
            })
            post['thumbs_by_me'] = bool(db.likes.find_one({
                'post_id': post['_id'],
                'type': 'thumbs',
                'username': payload["id"]
            }))
        return jsonify({
            'result': 'success',
            'msg': 'Berhasil mengambil semua posting',
            'posts': posts,
        })
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))


@app.route('/update_like', methods=['POST'])
def update_like():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )
        user_info = db.users.find_one({'username': payload.get('id')})
        post_id_receive = request.form.get('post_id_give')
        type_receive = request.form.get('type_give')
        action_receive = request.form.get('action_give')
        doc = {
            'post_id': post_id_receive,
            'username': user_info.get('username'),
            'type': type_receive
        }
        if action_receive == 'like':  # or action_receive == 'star' or action_receive == 'thumbs'
            db.likes.insert_one(doc)
        else:
            db.likes.delete_one(doc)

        count = db.likes.count_documents({
            'post_id': post_id_receive,
            'type': type_receive
        })

        return jsonify({
            'result': 'success',
            'msg': 'Diperbarui!',
            'count': count
        })
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for('home'))


@app.route('/about', methods=['GET'])
def about():
    return render_template('about.html')


@app.route('/secret', methods=['GET'])
def secret():
    token_receive = request.cookies.get(TOKEN_KEY)
    try:
        payload = jwt.decode(
            token_receive,
            SECRET_KEY,
            algorithms=['HS256']
        )
        user_info = db.users.find_one({'username': payload.get('id')})
        return render_template('secret.html', user_info=user_info)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return render_template('secret2.html')


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)
