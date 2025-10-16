import requests
import time
import json
import sys
import csv
import re
import os
from datetime import datetime

# 定数定義
BASE_URL = "https://kokkai.ndl.go.jp/api/speech"
MAX_RECORDS_PER_REQUEST = 100
DEFAULT_FROM_DATE = "2020-09-01"
DEFAULT_UNTIL_DATE = "2020-09-30"
REQUEST_DELAY = 0.5  # API負荷軽減のための待機時間（秒）
DATE_PATTERN = r'^\d{4}-\d{2}-\d{2}$'
DATASET_DIR = "dataset"  # 出力先のベースディレクトリ

# URLパラメータ用の辞書を空の状態で用意し、後から順次格納する
# params_count: ヒット総数の確認用、params_data: データ取得用
params_count = {} 
params_data = {}

# 検索条件を記録するための辞書
search_conditions = {}

# パラメータを対話的に入力する
print("=== 国会会議録検索システム データ取得ツール ===")
print("各項目を入力してください（不要な場合はEnterキーでスキップ）")

# 検索文字列の入力
text_input = input('検索する文字列を入力 >> ').strip()
if text_input:
    params_count['any'] = text_input
    params_data['any'] = text_input
    search_conditions['検索文字列'] = text_input
else:
    search_conditions['検索文字列'] = '指定なし'

# 院名の入力
house_input = input('検索する院名を入力（衆議院/参議院） >> ').strip()
if house_input:
    params_count['nameOfHouse'] = house_input
    params_data['nameOfHouse'] = house_input
    search_conditions['院名'] = house_input
else:
    search_conditions['院名'] = '指定なし'

# 発言者名の入力
speaker_input = input('検索する発言者名を入力 >> ').strip()
if speaker_input:
    params_count['speaker'] = speaker_input
    params_data['speaker'] = speaker_input
    search_conditions['発言者名'] = speaker_input
else:
    search_conditions['発言者名'] = '指定なし'

# 開始日の入力と検証
from_input = input(f'開始日を入力 (YYYY-MM-DD形式, 例: {DEFAULT_FROM_DATE}) >> ').strip()
if re.match(DATE_PATTERN, from_input):
    params_count['from'] = from_input
    params_data['from'] = from_input
    search_conditions['開始日'] = from_input
else:
    params_count['from'] = DEFAULT_FROM_DATE
    params_data['from'] = DEFAULT_FROM_DATE
    search_conditions['開始日'] = DEFAULT_FROM_DATE
    if from_input:
        print(f"⚠️ 無効な日付形式です。開始日を {DEFAULT_FROM_DATE} に設定しました。")
    else:
        print(f"開始日を {DEFAULT_FROM_DATE} に設定しました。")

# 終了日の入力と検証
until_input = input(f'終了日を入力 (YYYY-MM-DD形式, 例: {DEFAULT_UNTIL_DATE}) >> ').strip()
if re.match(DATE_PATTERN, until_input):
    params_count['until'] = until_input
    params_data['until'] = until_input
    search_conditions['終了日'] = until_input
else:
    params_count['until'] = DEFAULT_UNTIL_DATE
    params_data['until'] = DEFAULT_UNTIL_DATE
    search_conditions['終了日'] = DEFAULT_UNTIL_DATE
    if until_input:
        print(f"⚠️ 無効な日付形式です。終了日を {DEFAULT_UNTIL_DATE} に設定しました。")
    else:
        print(f"終了日を {DEFAULT_UNTIL_DATE} に設定しました。")

# ヒット件数確認用のパラメータ設定
params_count['maximumRecords'] = 1
params_count['recordPacking'] = "json"

print("\n検索条件でヒット件数を確認しています...")

try:
    # APIにリクエストを送信してヒット件数を取得
    response_count = requests.get(BASE_URL, params_count, timeout=30)
    response_count.raise_for_status()  # HTTPエラーをチェック
    
    json_data_count = response_count.json()
    
    # レスポンスに含まれているヒット件数を確認
    if "numberOfRecords" not in json_data_count:
        print("⚠️ エラー: APIレスポンスにヒット件数が含まれていません。検索条件を確認してください。")
        sys.exit(1)
    
    total_num = json_data_count["numberOfRecords"]
    
    # 検索条件に実行情報を追加
    search_conditions['実行日時'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    search_conditions['ヒット件数'] = total_num
    
except requests.exceptions.RequestException as e:
    print(f"⚠️ ネットワークエラー: {e}")
    sys.exit(1)
except json.JSONDecodeError:
    print("⚠️ エラー: APIレスポンスのJSON解析に失敗しました。")
    sys.exit(1)
except Exception as e:
    print(f"⚠️ 予期しないエラーが発生しました: {e}")
    sys.exit(1)

# 件数を表示し、データ取得を続行するか確認をとる
print(f"\n✅ 検索結果: {total_num:,}件")

if total_num == 0:
    print("検索条件にマッチするデータがありません。")
    sys.exit(0)

next_input = input(f"データを取得しますか？ (キャンセルする場合は 'n' を入力) [Y/n] >> ").strip().lower()
if next_input in ['n', 'no', 'キャンセル']:
    print('プログラムをキャンセルしました。')
    sys.exit(0)

# データ取得の準備
print(f"\nデータ取得を開始します... (合計 {total_num:,}件)")

# ヒットした全件を取得するために必要なリクエスト回数を算出
total_pages = (total_num + MAX_RECORDS_PER_REQUEST - 1) // MAX_RECORDS_PER_REQUEST

# 全件取得用のパラメータを設定
params_data['maximumRecords'] = MAX_RECORDS_PER_REQUEST
params_data['recordPacking'] = "json"

# 取得データを格納するためのリストを用意
records = []

# 全件取得するためのループ処理
for page in range(total_pages):
    try:
        # 開始レコード番号を計算
        start_record = 1 + (page * MAX_RECORDS_PER_REQUEST)
        params_data['startRecord'] = start_record
        
        # APIにリクエストを送信
        response_data = requests.get(BASE_URL, params_data, timeout=30)
        response_data.raise_for_status()
        
        json_data = response_data.json()
        
        # レスポンスにデータが含まれているか確認
        if 'speechRecord' not in json_data or not json_data['speechRecord']:
            print(f"\n⚠️ ページ {page + 1} にデータがありません。")
            break
        
        # JSONデータ内の各発言データから必要項目を抽出してリストに格納
        for speech_record in json_data['speechRecord']:
            # 発言内容の改行コードを半角スペースに置換
            speech_text = speech_record.get('speech', '').replace('\r\n', ' ').replace('\n', ' ')
            
            record = [
                speech_record.get('speechID', ''),
                speech_record.get('issueID', ''),
                speech_record.get('imageKind', ''),
                speech_record.get('nameOfHouse', ''),
                speech_record.get('nameOfMeeting', ''),
                speech_record.get('issue', ''),
                speech_record.get('date', ''),
                speech_record.get('speechOrder', ''),
                speech_record.get('speaker', ''),
                speech_record.get('speakerGroup', ''),
                speech_record.get('speakerPosition', ''),
                speech_record.get('speakerRole', ''),
                speech_text,
                speech_record.get('speechURL', ''),
                speech_record.get('meetingURL', '')
            ]
            records.append(record)
        
        # 進捗状況を表示
        progress = ((page + 1) / total_pages) * 100
        sys.stdout.write(f"\r進捗: {page + 1}/{total_pages} ページ ({progress:.1f}%) - 取得済み: {len(records):,}件")
        sys.stdout.flush()
        
        # API負荷軽減のための待機
        time.sleep(REQUEST_DELAY)
        
    except requests.exceptions.RequestException as e:
        print(f"\n⚠️ ページ {page + 1} の取得中にネットワークエラーが発生しました: {e}")
        break
    except Exception as e:
        print(f"\n⚠️ ページ {page + 1} の処理中にエラーが発生しました: {e}")
        break

print(f"\n\n✅ データ取得完了: {len(records):,}件を取得しました。")

# 出力フォルダの作成とファイル保存
if records:
    # タイムスタンプを生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 出力フォルダ名を生成
    folder_name = f"kokkai_speech_{len(records)}_{timestamp}"
    output_dir = os.path.join(DATASET_DIR, folder_name)
    
    try:
        # datasetディレクトリが存在しない場合は作成
        if not os.path.exists(DATASET_DIR):
            os.makedirs(DATASET_DIR)
            print(f"📁 {DATASET_DIR} ディレクトリを作成しました。")
        
        # 出力用フォルダを作成
        os.makedirs(output_dir, exist_ok=True)
        print(f"📁 出力フォルダを作成しました: {output_dir}")
        
        # CSVファイルのパスを生成
        csv_filename = f"kokkai_speech_{len(records)}_{timestamp}.csv"
        csv_filepath = os.path.join(output_dir, csv_filename)
        
        # CSVファイルを保存
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as f:
            csvwriter = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_NONNUMERIC)
            
            # ヘッダーを書き込み
            headers = [
                '発言ID', '会議録ID', '種別', '院名', '会議名', '号数', 
                '日付', '発言番号', '発言者名', '発言者所属会派', 
                '発言者肩書き', '発言者役割', '発言内容', '発言URL', '会議録URL'
            ]
            csvwriter.writerow(headers)
            
            # データを書き込み
            for record in records:
                csvwriter.writerow(record)
        
        print(f"✅ CSVファイルを保存しました: {csv_filepath}")
        
        # 検索条件ファイルのパスを生成
        conditions_filename = f"search_conditions_{timestamp}.txt"
        conditions_filepath = os.path.join(output_dir, conditions_filename)
        
        # 検索条件をテキストファイルに保存
        with open(conditions_filepath, 'w', encoding='utf-8') as f:
            f.write("=== 国会会議録検索システム 検索条件 ===\n\n")
            for key, value in search_conditions.items():
                f.write(f"{key}: {value}\n")
            f.write(f"\n=== 取得結果 ===\n")
            f.write(f"実際の取得件数: {len(records):,}件\n")
            f.write(f"CSVファイル名: {csv_filename}\n")
            f.write(f"出力フォルダ: {folder_name}\n")
        
        print(f"✅ 検索条件ファイルを保存しました: {conditions_filepath}")
        print(f"📊 取得データ数: {len(records):,}件")
        print(f"📁 出力フォルダ: {output_dir}")
        
    except Exception as e:
        print(f"\n⚠️ ファイル保存中にエラーが発生しました: {e}")
        sys.exit(1)
else:
    print("\n⚠️ 取得できたデータがありません。")

print("\nプログラムが正常に終了しました。")
