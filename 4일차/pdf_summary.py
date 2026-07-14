import os
from dotenv import load_dotenv
import pymupdf
from openai import OpenAI

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# import os
# pdf_path = "/Users/user/Desktop/cursor 연습/4일차/samples/Language_models.pdf"

# print("전체:", pdf_path)
# print("폴더:", os.path.dirname(pdf_path))
# print("파일명:", os.path.basename(pdf_path))
# print("이름만:", os.path.splitext(os.path.basename(pdf_path))[0])

def pdf_to_text(pdf_path): #pdf 파일을 txt 파일로 변환하고, 거기에 full_text를 저장하는 함수
    doc = pymupdf.open(pdf_path)
    full_text = ''
    for page in doc:
        text = page.get_text()
        full_text += text + '\n------------------------\n'

    pdf_file_name = os.path.basename(pdf_path) #경로를 인식해서 파일만 가져오게됨(ex: ~~~.pdf)
    pdf_file_name = os.path.splitext(pdf_file_name)[0] #파일 확장자 제거
    #os.path.splitext(ABC.pdf) -> (ABC, .pdf)이므로 앞에 의미있는 [0]만 가져오기
    txt_file_path = os.path.join(os.path.dirname(pdf_path), f'{pdf_file_name}.txt') #파일 경로 생성
    #os.path.dirname(pdf_path) -> 폴더 경로만 가져온다 (ex: /Users/user/Desktop/cursor 연습/4일차/samples)
    #os.path.join(폴더, 파일명) -> 폴더와 파일명을 합쳐서 경로 생성 (ex: /Users/user/Desktop/cursor 연습/4일차/samples/ABC.txt)
    with open(txt_file_path, 'w', encoding='utf-8') as f: #파일 쓰기
        f.write(full_text)

    return txt_file_path

def summarize_txt(txt_file_path): #full text txt 파일을 읽어서 summary 내용을 생성하는 함수
    client = OpenAI(api_key=api_key)
    with open(txt_file_path, 'r', encoding='utf-8') as f:
        txt = f.read()

    system_prompt = f'''
    너는 다음 글을 요약하는 봇이다. 아래 글을 읽고, 

    작성해야 하는 포맷은 다음과 같음
    # 제목

    ## 저자의 문제 인식 및 주장 (15문장 이내)

    ## 저자 소개


    ============= 이하 텍스트 ================
    {txt[:10000]}

    '''

    response = client.chat.completions.create(
        model = 'gpt-4o-mini',
        temperature = 0.1,
        messages=[
            {"role":"system","content":system_prompt},
        ]
    )

    return response.choices[0].message.content

def summarize_pdf(pdf_path): #summary 내용은 summarize_txt 실행으로 이미 나왔고, 이를 txt 파일로 저장하는 함수도 포함되어있음
    txt_file_path = pdf_to_text(pdf_path)
    summary = summarize_txt(txt_file_path)
    summary_file_name = os.path.splitext(os.path.basename(pdf_path))[0] + '_summary.txt' #summary_file_name = ABC_summary.txt 
    summary_file_path = os.path.join(os.path.dirname(pdf_path), summary_file_name) #summary_file_path = /Users/user/Desktop/cursor 연습/4일차/samples/ABC_summary.txt
    with open(summary_file_path, 'w', encoding='utf-8') as f:
        f.write(summary)
    return summary


if __name__ == "__main__": #이 파일을 직접 실행했을 떄만 test 돌리게 하는 코드
    pdf_path = os.path.join(os.getcwd(),"samples/Language_models.pdf")
    summary = summarize_pdf(pdf_path)
    print(summary)
    print("성공적으로 요약되었습니다.")
