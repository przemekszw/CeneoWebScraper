from app import app
import os
import json
import requests
import pandas as pd
from matplotlib import pyplot as plt
from bs4 import BeautifulSoup
from flask import render_template, redirect, url_for, request

def extract_element(ancestor, selector, attribute=None, return_list=False):
    try:
        if attribute:
            return ancestor.select_one(selector)[attribute]
        elif return_list:
            return [item.text.strip() for item in ancestor.select(selector)]
        else:
            return ancestor.select_one(selector).text.strip()
    except (AttributeError, TypeError):
        return None

review_elements = {
    "author": ["span.user-post__author-name"],
    "recommendation": ["span.user-post__author-recomendation > em"],
    "stars": ["span.user-post__score-count"],
    "content": ["div.user-post__text"],
    "publish_date": ["span.user-post__published > time:nth-child(1)", "datetime"],
    "purchase_date": ["span.user-post__published > time:nth-child(2)", "datetime"], 
    "useful": ["button.vote-yes > span"], 
    "useless": ["button.vote-no > span"],
    "pros": ["div.review-feature__title--positives ~ div.review-feature__item", None, True],
    "cons": ["div.review-feature__title--negatives ~ div.review-feature__item", None, True]
}

@app.route('/')
def index():
    return render_template("index.html.jinja")

@app.route('/author')
def author():
    return render_template("author.html.jinja")

@app.route('/extract', methods=["POST", "GET"])
def extract():
    if request.method == "POST":
        product_id = request.form.get("product_id")
        url = f"https://www.ceneo.pl/{product_id}#tab=reviews"
        all_reviews = []
        while(url):
            response = requests.get(url)
            page_dom = BeautifulSoup(response.text, 'html.parser')
            reviews = page_dom.select("div.js_product-review")
            for review in reviews:
                single_review = {key:extract_element(review, *values)
                                for key, values in review_elements.items()}
                single_review["review_id"] = review["data-entry-id"]

                single_review["recommendation"] = True if single_review["recommendation"] == "Polecam" else False if single_review["recommendation"] == "Nie polecam" else None
                single_review["stars"] = float(single_review["stars"].split("/").pop(0).replace(",", "."))
                single_review["useful"] = int(single_review["useful"])
                single_review["useless"] = int(single_review["useless"])
                single_review["publish_date"] = single_review["publish_date"].split(" ").pop(0) if single_review["publish_date"] is not None else None
                single_review["purchase_date"] = single_review["purchase_date"].split(" ").pop(0) if single_review["purchase_date"] is not None else None
                all_reviews.append(single_review)
            try: 
                next_page = page_dom.select_one("a.pagination__next")
                url = "https://www.ceneo.pl"+next_page["href"]
            except TypeError: url = None
        if not os.path.exists("app/reviews"):
            os.makedirs("app/reviews")
        with open(f"./app/reviews/{product_id}.json", "w", encoding="UTF-8") as f:
            json.dump(all_reviews, f, indent=4, ensure_ascii=False)
        return redirect(url_for('product', product_id=product_id))
    else:
        return render_template("extract.html.jinja")

@app.route('/products')
def products():
    if os.path.exists("app/reviews"):
        products = [item.split(".").pop(0) for item in os.listdir("app/reviews")]
    else:
        products = []
    return render_template("products.html.jinja", products=products)

@app.route('/product/<product_id>')
def product(product_id):
    reviews = pd.read_json(f"app/reviews/{product_id}.json")
    stats = {
        "product_rating": reviews.stars.mean().round(2),
        "reviews_count": reviews.shape[0],
        "pros_count": reviews.pros.map(bool).sum(),
        "cons_count": reviews.cons.map(bool).sum()
    }
    if not os.path.exists("app/static/plots"):
        os.makedirs("app/static/plots")
    recommendations = reviews.recommendation.value_counts(dropna = False)
    recommendations.plot.pie()
    plt.savefig(f"app/static/plots/{product_id}_recommendation.png")
    plt.close()
    return render_template("product.html.jinja", stats=stats, product_id=product_id, tables=[reviews.to_html(classes='table table-sm table-hover table-bordered', header="true", table_id="reviews")])