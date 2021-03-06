# %%
from multiprocessing import Pool
from bs4 import BeautifulSoup, element
from private.extract_3_dl_images import get_filename as get_image_filename, get_image_urls
from util import sqlite_db, db, data_dir
import re
import json
from tqdm import tqdm

dbo = sqlite_db(data_dir / "processed_data.sqlite3")

dbo.executescript(
    """
    create table if not exists recipes (
        id text primary key not null,
        data json
    );
    """
)

hacks = {
    "2138891343740724": {"<die Bananen": "die Bananen"},
    "2145411344764077": {"<Ober/Unterhitze>": "Ober/Unterhitze"},
    "2145631344777523": {"<Ober/Unterhitze>": "Ober/Unterhitze"},
    "2145691344778506": {"<Ober/Unterhitze>": "Ober/Unterhitze"},
    "2146291344873262": {"<Ober/Unterhitze> ": "Ober/Unterhitze"},
    "521931148551407": {"<lässt": "lässt", "<Achtung": "Achtung"},
    "518081147965129": {"<er soll": "er soll"},
    "278361105753843": {"<b>Für den Boden:<b/>": "Für den Boden:"},
    "337561117465209": {"<Menge nach Geschmack>": "(Menge nach Geschmack)"},
    "83641032797388": {"<blind backen>": "blind backen"},
    "2451521386106352": {"<- Stä": "- Stä"},
    "2148361345126605": {"<ca.": "ca.", "<Ober/Unterhitze>": "Ober/Unterhitze"},
    "501571145006172": {"<mit der": "mit der"},
    "73751027840697": {"<b>Tipp:": "Tipp:"},
}


def strip_spaces(text: str):
    return re.sub(r"\s+", " ", text.strip())


def parse_rating(text: str):
    text = re.sub(r"\s", "", text)
    rating = 0
    for c in text:
        if c == "\uE838":
            rating += 1
        elif c == "\uE839":
            rating += 0.5
    return rating


def parse_text(soup, id):
    text = ""
    for child in soup.select_one("#content .content-left"):
        if type(child) == element.NavigableString:
            text += strip_spaces(child)
            continue
        elif type(child) == element.Tag:
            if child.name == "br":
                text += "\n"
                continue
            elif child.name == "table":
                return text
    raise Exception(f"r{id} unknown thing {child}")


def parse_preparetime(txt: str):
    match = re.match(
        r"^ca.( (?P<days>\d+) Tage?)?( (?P<hours>\d+) Std.)?( (?P<minutes>\d+) Min.)?$",
        txt,
    )
    if match is None:
        raise Exception(f"could not match time {txt}")
    days = match.group("days") or "0"
    hours = match.group("hours") or "0"
    minutes = match.group("minutes") or "0"
    return float(days) * 60 * 24 + float(hours) * 60 + float(minutes)


def parse_mintbl(soup):
    tbl = [
        [strip_spaces(col.get_text()) for col in row.select("> td")]
        for row in soup.select("table#recipe-info > tr")
    ]
    tbl = {a: b for a, b in tbl}
    renames = dict(
        workingtime_min="Arbeitszeit:",
        cookingtime_min="Koch-/Backzeit:",
        restingtime_min="Ruhezeit:",
        kcal_per_portion="Kalorien p. P.:",
        difficulty="Schwierigkeitsgrad:",
    )

    def pkcal(kcal):
        if kcal == "keine Angabe":
            return None
        return float(re.match(r"^ca (\d+)$", kcal.replace(".", "")).group(1))

    procs = dict(
        workingtime_min=parse_preparetime,
        cookingtime_min=parse_preparetime,
        restingtime_min=parse_preparetime,
        kcal_per_portion=pkcal,
        difficulty=lambda x: x,
    )

    out = {}
    for ok, ik in renames.items():
        if ik in tbl:
            out[ok] = procs[ok](tbl[ik])
            del tbl[ik]
        else:
            out[ok] = None
    if len(tbl) > 0:
        raise Exception(f"unused keys {tbl}")
    return out


def get_ingredients(soup):
    ing_tbl = soup.select("#content table.incredients tr")
    ingredients = []
    for row in ing_tbl:
        left, right = row.select("> td")
        if len(right.select("b")) > 0:
            if strip_spaces(left.get_text()) != "":
                raise Exception(f"can't handle {row}")
            ingredients.append({"subtitle": strip_spaces(right.get_text())})
        else:
            ingredients.append(
                {
                    "amount": strip_spaces(left.get_text()),
                    "ingredient": strip_spaces(right.get_text()),
                }
            )
    return ingredients


def get_meta(recipe_id):
    if (
        dbo.execute(
            "select count(*) from recipes where id = ?", (recipe_id,)
        ).fetchone()[0]
        > 0
    ):
        return
    # print("get_images", recipe_id)
    canonical_url, index_html, detail_html = db.execute(
        "select canonical_url, index_html,detail_html from recipes where id=?",
        (recipe_id,),
    ).fetchone()

    for f, t in hacks.get(recipe_id, {}).items():
        detail_html = detail_html.replace(f, t)
    isoup = BeautifulSoup(index_html, "lxml")
    soup = BeautifulSoup(detail_html, "lxml")
    image_urls = get_image_urls(soup)
    image_filenames = [get_image_filename(url) for url in image_urls]
    for basename in image_filenames:
        filename = data_dir / "img" / basename
        if not filename.exists():
            print(f"warning: missing image for recipe {recipe_id}: {filename}")

    subtitle = soup.select_one("#content > p > strong")
    ingredients = get_ingredients(soup)

    ztt = soup.select_one("#content > .content-right > h3")
    rating_count = isoup.select_one("div.ds-rating-count > span:nth-of-type(2)")
    processed_data = {
        "id": recipe_id,
        "date": strip_spaces([*isoup.select_one("span.recipe-date")][1]),
        "canonical_url": canonical_url,
        "title": strip_spaces(soup.select_one("#content > h1").get_text()),
        "subtitle": strip_spaces(subtitle.get_text()) if subtitle else None,
        "tags": [],  # annoying to get these from the print page
        "rating": parse_rating(isoup.select_one("div.ds-rating-stars").get_text()),
        "rating_count": int(
            rating_count.get_text().replace("(", "").replace(")", "").replace(".", "")
        ),
        "portions": float(
            re.match(r"Zutaten für (\d+) Portion", strip_spaces(ztt.get_text())).group(
                1
            )
        ),
        "ingredients": ingredients,
        "recipe_text": parse_text(soup, recipe_id),
        "author": strip_spaces(
            soup.select_one("#content > .content-right")
            .find("strong", string="Verfasser:")
            .next_sibling
        ),
        **parse_mintbl(soup),
        "picture_urls": image_urls,
        "picture_files": image_filenames,
    }
    with dbo:
        dbo.execute(
            "insert into recipes (id, data) values (?, ?)",
            (recipe_id, json.dumps(processed_data, ensure_ascii=False)),
        )


def get_meta_p(r):
    try:
        return get_meta(r)
    except Exception as e:
        print(f"{r} failed: {e}")


# %%
if __name__ == "__main__":
    missing_recipes = db.cursor().execute("select id from recipes")

    # print(f"getting {missing_recipes.rowcount} recipes")
    id_list = [recipe["id"] for recipe in missing_recipes]

    with Pool(10) as p:
        data = list(p.imap(get_meta_p, tqdm(id_list), chunksize=100))
