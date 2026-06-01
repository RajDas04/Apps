import re, json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from datetime import datetime

class Scraper:
    def __init__(self, url):
        self.url = url
        self.play = None
        self.browser = None
        self.page = None

    def start_browser(self):
        self.play = sync_playwright().start()
        self.browser = self.play.chromium.launch()
        self.page = self.browser.new_page()
        self.page.goto(self.url)

    def close_browser(self):
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.play:
            self.play.stop()
        self.browser = None
        self.play = None
        self.page = None
    
    def search_products(self, search):
        self.start_browser()
        try:
            self.page.locator("input[name='q']:not([readonly])").fill(search) 
            # flipkart can change that placeholder text anytime which break your scraper, name="q" attribute on a search input, it's tied to form submission semantics
            self.page.keyboard.press('Escape') # this to escape bot or login checks
            self.page.keyboard.press('Enter')
            self.page.wait_for_load_state("networkidle")
            
            soup = BeautifulSoup(self.page.content(), "html.parser")

            # with open("output2.html", "w", encoding="utf-8") as f: # for debug
            #     f.write(soup.prettify())
            # ss = self.page.screenshot(path="example.png") # for debug
            return self.extract_prices(soup)
        
        except Exception as e:
            print(f"Skipped due to {e}")
        finally:
            self.close_browser()
    
    def extract_prices(self, soup: BeautifulSoup) -> list[dict]: # also extract product image
        result = []
        products = soup.find_all("div", attrs={"data-id": True})

        for product in products:
            try:
                data_id = product.get("data-id")
                img = product.find("img")
                name = img.get("alt", "").strip() if img else None
                image_url = img.get("src") if img else None
                price_tag = product.find("div", class_=re.compile(r"\bhZ3P6w\b"))
                mrp_tag = product.find("div", class_=re.compile(r"\bkRYCnD\b"))
                link_tag = product.find("a", class_="GnxRXv")
                if not link_tag: # just if the class doesn't match, any link inside the product section
                    link_tag = product.find("a", href=True)

                price = int(re.sub(r"[^\d]", "",price_tag.get_text(strip=True))) if price_tag else None
                mrp = int(re.sub(r"[^\d]", "",mrp_tag.get_text(strip=True))) if mrp_tag else None
                p_url = None
                if link_tag and link_tag.get("href"):
                    href = link_tag["href"]
                    p_url = f"https://www.flipkart.com{href.split('&')[0]}"

                if name and price and mrp:
                    result.append({"product": name, "price": price, "mrp": mrp, "url": p_url,
                                   "data_id": data_id, "image_url": image_url,
                                   "updated_on": datetime.now().strftime('%d-%m-%Y, %H:%M')})

            except Exception as e:
                print(f"Skipped due to {e}")
                continue

        return result
    
    def search_and_extract_prices_by_url(self, url: str) -> dict | None: # later a extract product using shared link
        self.start_browser()
        try:
            self.page.goto(url, timeout=30000)
            self.page.wait_for_load_state("networkidle")

            soup = BeautifulSoup(self.page.content(), "html.parser")

            ld = json.loads(soup.find("script", type="application/ld+json").string)
            # name = ld[0]["name"]
            price_tag = ld[0]["offers"]["price"] # it fetches directly product description so its reliable
            mrp_tag = soup.select_one('div.v1zwn21m.v1zwn21._1psv1zeb9._1psv1ze0') # but its not

            price = int(re.sub(r"[^\d]", "", str(price_tag))) if price_tag else None
            mrp = int(re.sub(r"[^\d]", "", mrp_tag.get_text(strip=True))) if mrp_tag else price
            # if mrp unavailable then price is mrp e.g iphones are fixed price
            return {"price": price, "mrp": mrp,
                    "updated_on": datetime.now().strftime('%d-%m-%Y, %H:%M')}
            
        except Exception as e:
            print(f"url fetch failed for {url}: {e}")
            return None
        finally:
            self.close_browser()

# for testing
if __name__ == "__main__":
    url = "https://www.flipkart.com"
    scraper = Scraper(url)
    search = input("Enter the Product: ")
    products = scraper.search_products(search)

    if not products:
        print(f"Found {len(products)} product cards but extracted 0 results. OR")
        print("No products found. Flipkart may have changed their CSS classes — inspect the page and update the regex patterns.")
    else:
        for i, p in enumerate(products, 1):
            print(f"{i}. {p['data_id']} {p['product']} — {p['price']} <- {p['mrp']}> {p['url']} | Image: {p['image_url']}")
    # for p in products[:3]:
    #     print(f"{p['data_id']}: {p.get('url', 'NO URL FOUND')}")