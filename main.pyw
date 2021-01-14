import tkinter as tk
import tkinter.ttk as ttk
from matplotlib import pyplot, image
import numpy as np
from openpyxl import Workbook
import socket
import json
from pathlib import Path
from threading import Thread
from multiprocessing import Manager, Lock
from PIL import Image, ImageTk



class GUI(object):
    def __init__(self, shared, lock, master=None):
        self.shared = shared
        self.lock = lock
        self.Alive = True
        # build ui
        self.toplevel_1 = tk.Tk()
        self.frame_1 = ttk.Frame(self.toplevel_1)
        self.canvas_1 = tk.Canvas(self.frame_1, width=300, height = 300)
        vimage = ImageTk.PhotoImage(Image.new('RGB',(300,300),'#121212'))
        self.imageoncanvas = self.canvas_1.create_image(0,0,anchor='nw',image=vimage)
        self.canvas_1.pack(expand='true', side='bottom')
        self.button_1 = ttk.Button(self.frame_1)
        self.button_1.config(text='StartLogging', command = lambda obj = self, key = 'StartLogging':obj.Button(obj,key))
        self.button_1.pack(side='left')
        self.button_2 = ttk.Button(self.frame_1)
        self.button_2.config(text='SaveToXLS', command = lambda obj = self, key = 'SaveToXLS':obj.Button(obj,key))
        self.button_2.pack(side='left')
        self.button_3 = ttk.Button(self.frame_1, command = lambda obj = self, key = 'Tar':obj.Button(obj,key))
        self.button_3.config(text='Tar')
        self.button_3.pack(side='left')
        self.button_4 = ttk.Button(self.frame_1)
        self.button_4.config(text='ZERO', command = lambda obj = self, key = 'ZERO':obj.Button(obj,key))
        self.button_4.pack(side='left')
        self.labelframe_1 = ttk.Labelframe(self.frame_1)
        self.text_1 = tk.Text(self.labelframe_1)
        self.text_1.config(height='1', width='15')
        self.text_1.pack(side='top')
        self.labelframe_1.config(text='Current Value')
        self.labelframe_1.pack(side='top')
        self.label_1 = ttk.Label(self.frame_1)
        self.label_1.config(text='')
        self.label_1.pack(anchor='s', side='bottom')
        self.frame_1.config(height='200', width='200')
        self.frame_1.pack(side='top')
        self.toplevel_1.title('Weight Scale')
        self.toplevel_1.config( height='200', width='200')

        # Main widget
        self.root = self.toplevel_1
        self.root.after(300, self.refresh)
        self.mainloop()

    def refresh(self):
        self.lock.acquire()
        currentVal = self.shared['Values']['CurrentWeight']
        image = self.shared['Values']['image']
        label = self.shared['Values']['label']
        self.lock.release()
        self.text_1.delete('1.0',tk.END)
        self.text_1.insert('1.0',currentVal)
        self.canvas_1.itemconfig(self.imageoncanvas, image=ImageTk.PhotoImage(image))
        self.label_1.config(text=label)
        self.root.after(300, self.refresh)

    def Button(self, key):
        self.lock.acquire()
        self.shared['Buttons'][key] = True
        self.lock.release()

    def is_alive(self):
        return self.Alive

    def mainloop(self):
        while True:
            if not self.is_alive():
                break
            try:
                self.root.update()
            except:
                break

class Logger(object):
    def __init__(self, shared, lock):
        self.lock = lock
        self.shared = shared
        self.lock.acquire()
        self.socket = self.shared['socket']
        self.lock.release()
        if self.socket:
            self.socket.connect()
            self.mainloop()
        else:
            self.lock.acquire()
            self.shared['Values']['label'] = 'Unable to connect with weight scale'
            self.lock.release()

    def mainloop(self):
        while True:
            self.lock.acquire()
            start = self.shared['Buttons']['StartLogging']
            Tar = self.shared['Buttons']['Tar']
            ZERO = self.shared['Buttons']['ZERO']
            logging = self.shared['State']['Logging']
            self.lock.release()
            if start: self.start(logging)
            if Tar: self.Tar()
            if ZERO: self.ZERO()
            if logging: self.logging()

    def start(self, alreadyrunning):
        self.socket.sendall('CU'+str(int(alreadyrunning))+' /r/n')
        response = ''
        while True:
            response += self.socket.recv(8)
            if '/r/n' in response:
                break
            if not self.framecoherent(response):
                break
        self.lock.acquire()
        self.shared['Buttons']['StartLogging'] = False
        self.lock.release()

    def framecoherent(self, frame):
        if 'ES' in frame:
            self.lock.acquire()
            self.shared['Values']['label'] = 'Invalid command'
            self.lock.release()
            return False
        if frame[0] in ['Z','T']:
            try:
                if not frame[1] == ' ':
                    return False
                if not frame[2] in ['A','D','^','v','I']:
                    return False
                else:
                    self.lock.acquire()
                    self.shared['Values']['label'] = 'Weight returns '+frame[2]
                    self.lock.release()
                if not frame[3] == '/r':
                    return False
                if not frame[4] == '/n':
                    return False
            except:
                pass
            #TODO CU0/CU1
        return True



class App(object):
    def __init__(self):
        self.Alive = True
        self.configuration = json.load(open(str(Path(__file__).parent.absolute())+'\\config.json'))
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.configuration['Network']['IP'], self.configuration['Network']['port']))
        except:
            pass
        self.history = json.load(open(str(Path(__file__).parent.absolute())+'\\history.json'))
        self.shared = Manager()
        self.Lock = Lock()
        self.AppVariable = self.shared.dict({
            'socket':None if not hasattr(self,'socket') else self.socket,
            'Buttons':self.shared.dict({
                'StartLogging':False,
                'SaveToXLS':False,
                'Tar':False,
                'ZERO':False,
                'StableUnit':False,
                'CurrentValueUnit':False,
                'CU1':False,
                'CU0':False

            }),
            'State':self.shared.dict({
                'Logging':False,
                'Saving':False,
                'WeightScaleBusy':False
            }),
            'Values':self.shared.dict({
                'CurrentWeight':'0 kg',
                'image':Image.new('RGB',(300,300),'#af342f'),
                'label':'Err'
            })


        })
        self.Threads = [
            Thread(target = GUI, args = (self.AppVariable, self.Lock)),
            Thread(target = Logger, args = (self.AppVariable, self.Lock))

        ]
        

    def is_alive(self):
        return self.Alive

    def run(self):
        for thread in self.Threads: thread.start()
        for thread in self.Threads: thread.join()

if __name__=='__main__':
    Application = App()
    Application.run()