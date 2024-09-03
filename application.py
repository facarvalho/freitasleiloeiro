from typing import List
from playwright.sync_api import sync_playwright
import re
import csv
from playwright_recaptcha import recaptchav2
import environment as env



def to_float(text):
    return float(f"{text}".replace(".","").replace(",",".").replace("R$","").strip())
    
def get_links(page) -> List[str]:    
    page.goto(f"{env.base_url}/Leiloes/ListarLotes?LeilaoId={env.leilao_id}&Nome=&Lote=&Categoria=1&TipoLoteId=1&FaixaValor=2&Condicao=inteiros&PatioId=0&AnoModeloMin=0&AnoModeloMax=0&ArCondicionado=true&DirecaoAssistida=true&ClienteSclId=0&PageNumber=1&TopRows=500")        
    links=[]
    link_locators = page.locator('a').all()
    for _ in link_locators:
        link= f"{env.base_url}{_.get_attribute('href')}"
        if link not in links:
            links.append(link)
    return links

def get_lote(page, link):    
    page.goto(link)              
    desc=page.locator('[class="text-secondary pt-2 small"]').inner_text().upper()
    damaged=re.search("(?i)(?<=|^)DANOS ESTRUTURAIS|DANOS E REPAROS ESTRUTURAIS|MOTOR QUEIMANDO|TRINCADOMOTOR BATENDO|DANIFICAD(?=|$)",desc) is not None
    sinistro=re.search("(?i)(?<=|^)sinistrado(?=|$)",desc) is not None
    car = page.locator('[class="text-secondary d-flex flex-column"]').all()[0].locator("div").all()[0].inner_text().replace("\xa0","").strip()        
    lote = page.locator('[class="col-4 col-xl-3"]').all()[0].locator("div").all()[1].inner_text()
    date = page.locator('[class="col-4 col-xl-5"]').all()[0].locator("div").all()[1].inner_text()      
      
    start_value = to_float(page.locator('[class="col-6 text-center pe-1"]').all()[0].locator("div").all()[1].inner_text())            
    selled = to_float(page.locator('input#hdMaiorLance').all()[0].input_value())        
    
    
    tax_string=page.locator('[class="small text-secondary"]').all()[0].inner_text()
    p = re.compile("(?<=\$\s)[\d,.$]+")
    taxes = re.findall(p, tax_string)
    total_tax = 0
    for tax in taxes:   
        tax_float = to_float(tax)
        if (tax_float < 5000):         
            total_tax += tax_float    
    return {        
        "leilao_id": env.leilao_id,
        "date": date,
        "lote": lote,
        "target": 0,
        "car": car,        
        "fipe_min": 0,
        "fipe_max": 0,
        "start_value": start_value,        
        "target": 0,
        "total_target": 0,
        "discount": 0,
        "selled": selled,
        "total_tax": total_tax,
        "damaged": damaged,
        "sinistro": sinistro,
        "link": link
    }

def get_fipe(page, car_name) -> List[str]:    

    value_sting = []
    try:
        
        page.goto(f"https://www.google.com/search?q=fipe+{car_name}")   

        is_captcha_required = False
        for frame in page.frames:
            if 'not a robot' in frame.content():
                is_captcha_required = True
                break

        if is_captcha_required == True:
            with recaptchav2.SyncSolver(page) as solver:
                solver.solve_recaptcha(wait=True)
                

        text = page.locator('[id="rso"]').all()[0].locator("div").all()[0].inner_text()    
        p = re.compile("(?<=\$\s)[\d,.$]+")
        value_sting = re.findall(p, text)
           
    except Exception as ex:
        print(ex)
        print(car_name)
        return get_fipe(page, car_name)

    fipe_min = 9999999999999
    fipe_max = 0
    for val in value_sting:   
        val_float = to_float(val)
        if (val_float < fipe_min):         
            fipe_min = val_float  
        if (val_float > fipe_max):         
            fipe_max = val_float  
    return {
        "fipe_min":fipe_min,
        "fipe_max": fipe_max
    }

def add_target(lote):    
    
    total_tax = lote["total_tax"]
    fipe_min = lote["fipe_min"]
    fipe_max = lote["fipe_max"]    
    fipe = (fipe_min+fipe_max)/2            

    total_target = (1-env.discount/100)*fipe
    target = total_target-total_tax
    fee =  target/100*5
    target -= fee    
    
    lote["discount"] = f"{env.discount}%"
    lote["target"] = target
    lote["fee"] = fee
    lote["total_target"] = total_target


def main():
    cars=[]
    with sync_playwright() as playwright:        
        browser = playwright.chromium.launch(headless=False, slow_mo=50)                
        page = browser.new_page()        
        links:List[any] = get_links(page)
        c=0
        for link in links:
            c+=1            
            lote = get_lote(page, link)
            print(f"searching... {c}...{len(links)} {lote['car']} {link}")
            fipe = get_fipe(page,lote["car"])            
            lote.update(fipe)          
            add_target(lote)            
            cars.append(lote)                       
            
        browser.close()
    
    
    with open(f"leilao_{env.leilao_id}.csv", "w") as csvfile:
        writer = csv.writer(csvfile)
 
        columns = [ ]
        for car in cars:
            if not columns:                
                columns = car.keys()
                writer.writerow(columns)    
            row = [car[column] for column in columns]
            writer.writerow(row)

if __name__ == "__main__":    
     main()
     
    

    