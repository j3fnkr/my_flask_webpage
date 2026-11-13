import os
import sys

from flask import json
from jsonschema import validate, ValidationError, SchemaError

from app import app
from app.models import *

current_directory = os.path.dirname(os.path.abspath(__file__))


def recreate_tables():
    db.drop_all()
    db.create_all()


def validate_resources():
    resources = ("projects", "images")

    for file_name in resources:
        with (
            app.open_resource("../resource/{0}.json".format(file_name)) as fd_json,
            app.open_resource("../resource/{0}.schema".format(file_name)) as fd_schema,
        ):
            res_json = json.load(fd_json)
            res_schema = json.load(fd_schema)

            validate(res_json, res_schema)


def insert_resources():
    insert_projects_and_images("../resource/projects.json")
    insert_image_metadata("../resource/images.json")
    db.session.commit()


def insert_projects_and_images(json_file):
    with app.open_resource(json_file) as fd:
        json_ = json.load(fd)

        for project in json_["projects"]:
            img = project.pop("image", None)
            main_image = Gallery(**img)
            db.session.add(main_image)
            db.session.flush()

            img_folder = project.pop("img_folder", None)
            project_db = Project(**project, image_id=main_image.id)
            db.session.add(project_db)
            db.session.flush()

            # import other images from folder
            if img_folder:
                img_path = os.path.join(current_directory, "..", "app", "static", "img")
                img_path = os.path.abspath(img_path)
                for img in os.listdir("{0}/{1}".format(img_path, img_folder)):
                    if (
                        img.endswith((".jpg", ".png"))
                        and (img != main_image.src.split("/")[-1])
                        and ("banner" not in img)
                    ):  # exclude banner images from gallery
                        img_dict = {
                            "project_id": project_db.id,
                            "src": "img/{}/{}".format(img_folder, img),
                            "alt": img.split(".")[0],
                        }
                        img_db = Gallery(**img_dict)
                        db.session.add(img_db)
            db.session.flush()


def insert_image_metadata(json_file):
    with app.open_resource(json_file) as fd:
        json_ = json.load(fd)

        for image in json_["images"]:
            img_db = Gallery.query.filter_by(src=image["src"]).first()
            if img_db is not None:
                img_db.alt = image.pop("alt", None)
                img_db.cc = image.pop("cc", None)
                img_db.cc_author = image.pop("cc_author", None)
            else:
                print("Image '{0}' not found in database.".format(image["src"]))


if __name__ == "__main__":
    try:
        validate_resources()  # Strong exception safety guarantee
    except (ValidationError, SchemaError) as e:
        print(e)  # Stacktrace does not contain any useful information
        sys.exit()

    print("Resources are valid.")

    recreate_tables()
    print("Tables recreated.")

    insert_resources()

    print("Database initialized with resources.")
