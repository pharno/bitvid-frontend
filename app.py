# -*- coding: utf-8 -*-

from flask import Flask, render_template, session, request, flash, url_for, redirect, g
from flask.ext.classy import FlaskView, route

from client import HTTPClient
from pprint import pprint
import os
import time

app = Flask(__name__)


curr_env = os.environ.get("BITVID_ENV", "Dev")
app.config.from_object("config.{env}Config".format(env=curr_env))


def video_url(token, height, extention):
    return "{host}/videos/{token}_{height}.{ext}".format(
        host=app.config['HOST'], token=token, height=height, ext=extention)


def buildVideoFromJson(jsobj):
    try:
        if "message" in jsobj.keys():
            flash("could not load videos")
            return {}
    except:
        pass

    resultset = []
    for video in jsobj:
        actualvideos = {}
        videomedias = g.client.getVideo(str(video["token"]))
        if "message" in videomedias.keys():
            pass
        else:
            pprint(videomedias,indent=4)
            for videomedia in videomedias["videos"]:
                if videomedia["codec"] not in actualvideos.keys() or videomedia["height"] > actualvideos[videomedia["codec"]]["height"]:
                    print videomedia["codec"]
                    videomedia["path"] = video_url(video["token"], videomedia["height"], videomedia["codec"])
                    actualvideos[videomedia["codec"]] = videomedia

        video["medias"] = actualvideos
        resultset.append(video)

    pprint(resultset,indent=4)
    return resultset


def getVideosForQuery(query):
    data = g.client.search(query)
    pprint(data,indent=4)
    try:
        if "message" in data.keys():
            print "data", data
            flash("could not load videos")
            return {}
    except Exception as ex:
        print ex

    return buildVideoFromJson(data)

class IndexView(FlaskView):
    route_base = "/"

    def index(self):
        return redirect(url_for("VideoView:index"))


class AuthView(FlaskView):
    route_base = "/auth/"

    def get(self):
        return render_template("login.html")

    def post(self):
        user = request.form["username"]
        password = request.form["password"]

        try:
            success = g.client.authenticate(user, password)
        except:
            flash("could not login")
            return redirect(url_for("AuthView:get"))

        if "message" in success.keys():
            print "success", success
            flash(success["message"])
            return redirect(url_for("AuthView:get"))

        return redirect(url_for("IndexView:index"))

    @route("/logout", methods=["GET"]) # TODO, make this POST
    def logout(self):
        g.client.authtoken = None
        return redirect(url_for("IndexView:index"))


class RegisterView(FlaskView):
    route_base = "/auth/register"

    def get(self):
        return render_template("register.html")

    def post(self):
        user = request.form["username"]
        password = request.form["password"]
        password2 = request.form["password2"]

        if password != password2:
            flash("passwords do not match")
            return render_template("register.html")

        try:
            success = g.client.register(user, password)
        except:
            flash("could not register")
            return redirect(url_for("RegisterView:get"))

        if "message" in success.keys():
            print "success", success
            flash(success["message"])
            return redirect(url_for("RegisterView:get"))


        return redirect(url_for("IndexView:index"))




class UserView(FlaskView):
    def index(self):
        return render_template("user.html", user=g.client.getUser())

    def get(self, userid):
        return render_template("user.html", user=g.client.getUser(userid))


class VideoView(FlaskView):
    def index(self):
        query = request.args.get("q","*")
        videos = getVideosForQuery(query)

        return render_template("videolist.html",videos=videos)

    def get(self, videoid):
        video = getVideosForQuery("token:"+videoid)[0]
        comments = g.client.getCommentsForVideo(videoid)
        pprint(video,indent=4)
        return render_template("video.html",video=video,videoMedias=video["medias"], comments=comments)


class VideoUploadView(FlaskView):
    route_base = '/video/upload'

    def get(self):
        return render_template("video_upload.html")

    def post(self):
        title = request.form["title"]
        description = request.form["description"]
        video = g.client._getVideoToken(title, description)
        if "message" in video.keys():
            flash(video["message"])
            return redirect(url_for("VideoUploadView:get"))
        uploaddata = g.client.uploadVideo(video["token"], request.files["videofile"])

        if "message" in uploaddata.keys():
            print "uploaddata", uploaddata
            flash(uploaddata["message"])
            g.client.deleteVideo(video["token"])
            return redirect(url_for("VideoUploadView:get"))


        count = 20
        while count > 0:
            count -= 1
            time.sleep(0.1)
            try:
                getVideosForQuery("token:"+video["token"])[0]
                break
            except:
                pass
                # god is this ugly. waiting for the video to get indexed..

        return redirect(app.config["HOST"]+url_for('VideoView:get', videoid=video["token"]))

class VideoCommentView(FlaskView):
    def post(self):
        try:
            title = request.form["title"]
            content = request.form["content"]
            videotoken = request.form["videoToken"]
        except Exception as ex:
            print ex
            flash("missing either title, description or videotoken")

        comment = g.client.comment(title, content, videotoken)

        if "message" in comment.keys():
            flash(comment["message"])
        else:
            flash("comment posted successfully")

        return redirect(url_for("VideoView:get",videoid = videotoken))
IndexView.register(app)
AuthView.register(app)
RegisterView.register(app)
UserView.register(app)
VideoView.register(app)
VideoUploadView.register(app)
VideoCommentView.register(app)

@app.before_request
def before(*args, **kwargs):
    g.client = HTTPClient(app.config["API_URL"])
    if "client_token" in session:
        g.client.authtoken = session["client_token"]


@app.after_request
def after(response, **kwargs):
    print response, kwargs
    session["client_token"] = g.client.authtoken

    return response
if __name__ == '__main__':
    app.secret_key = 'change this secret key'
    app.run(port=8080, debug=True)
