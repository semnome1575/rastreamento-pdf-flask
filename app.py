==> Deploying...
==> Running 'gunicorn app:app'
[2025-10-07 23:03:50 +0000] [57] [INFO] Starting gunicorn 23.0.0
[2025-10-07 23:03:50 +0000] [57] [INFO] Listening at: http://0.0.0.0:10000 (57)
[2025-10-07 23:03:50 +0000] [57] [INFO] Using worker: sync
[2025-10-07 23:03:50 +0000] [65] [INFO] Booting worker with pid: 65
127.0.0.1 - - [07/Oct/2025:23:03:51 +0000] "HEAD / HTTP/1.1" 200 0 "-" "Go-http-client/1.1"
     ==> Your service is live 🎉
     ==> 
     ==> ///////////////////////////////////////////////////////////
     ==> 
     ==> Available at your primary URL https://pdf-rastreavel-app.onrender.com
     ==> 
     ==> ///////////////////////////////////////////////////////////
127.0.0.1 - - [07/Oct/2025:23:03:56 +0000] "GET / HTTP/1.1" 200 7414 "-" "Go-http-client/2.0"
127.0.0.1 - - [07/Oct/2025:23:04:04 +0000] "GET / HTTP/1.1" 200 7414 "-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
/opt/render/project/src/app.py:154: FutureWarning: Passing bytes to 'read_excel' is deprecated and will be removed in a future version. To read from a byte string, wrap it in a `BytesIO` object.
  df = pd.read_excel(file_bytes, engine='openpyxl')
DEBUG: Tentando ler arquivo Excel: dados_exemplo.xlsx
ERRO FATAL LEITURA EXCEL: Traceback (most recent call last):
  File "/opt/render/project/src/app.py", line 154, in upload_file
    df = pd.read_excel(file_bytes, engine='openpyxl')
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/pandas/io/excel/_base.py", line 495, in read_excel
    io = ExcelFile(
        io,
    ...<2 lines>...
        engine_kwargs=engine_kwargs,
    )
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/pandas/io/excel/_base.py", line 1567, in __init__
    self._reader = self._engines[engine](
                   ~~~~~~~~~~~~~~~~~~~~~^
        self._io,
        ^^^^^^^^^
        storage_options=storage_options,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        engine_kwargs=engine_kwargs,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/pandas/io/excel/_openpyxl.py", line 553, in __init__
    super().__init__(
    ~~~~~~~~~~~~~~~~^
        filepath_or_buffer,
        ^^^^^^^^^^^^^^^^^^^
        storage_options=storage_options,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        engine_kwargs=engine_kwargs,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/pandas/io/excel/_base.py", line 573, in __init__
    self.book = self.load_workbook(self.handles.handle, engine_kwargs)
                ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/pandas/io/excel/_openpyxl.py", line 572, in load_workbook
    return load_workbook(
        filepath_or_buffer,
        **(default_kwargs | engine_kwargs),
    )
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/openpyxl/reader/excel.py", line 346, in load_workbook
    reader = ExcelReader(filename, read_only, keep_vba,
                         data_only, keep_links, rich_text)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/openpyxl/reader/excel.py", line 123, in __init__
    self.archive = _validate_archive(fn)
                   ~~~~~~~~~~~~~~~~~^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/openpyxl/reader/excel.py", line 95, in _validate_archive
    archive = ZipFile(filename, 'r')
  File "/opt/render/project/python/Python-3.13.4/lib/python3.13/zipfile/__init__.py", line 1385, in __init__
    self._RealGetContents()
    ~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/python/Python-3.13.4/lib/python3.13/zipfile/__init__.py", line 1452, in _RealGetContents
    raise BadZipFile("File is not a zip file")
zipfile.BadZipFile: File is not a zip file
127.0.0.1 - - [07/Oct/2025:23:04:18 +0000] "POST /upload HTTP/1.1" 500 49 "https://pdf-rastreavel-app.onrender.com/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
[2025-10-07 23:04:54 +0000] [56] [INFO] Handling signal: term
[2025-10-07 23:04:54 +0000] [65] [INFO] Worker exiting (pid: 65)
[2025-10-07 23:04:55 +0000] [56] [INFO] Shutting down: Master
