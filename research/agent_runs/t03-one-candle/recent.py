import os,time,sys
root=r"C:\Users\aharg\Desktop"
now=time.time()
for dp,dn,fn in os.walk(root):
    dn[:]=[d for d in dn if d not in ('.git','node_modules','__pycache__','data_archive','.venv','venv')]
    for f in fn:
        p=os.path.join(dp,f)
        try:
            st=os.stat(p)
        except: continue
        if now-st.st_mtime<3600: print(int((now-st.st_mtime)/60),'min',st.st_size,p)
