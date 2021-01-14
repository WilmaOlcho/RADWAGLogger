import tkinter as tk
import tkinter.ttk as ttk
from matplotlib import pyplot, image
import numpy as np
from openpyxl import Workbook
import socket
import json
from pathlib import Path
from threading import Thread
from multiprocessing import Manager, Lock, freeze_support
from PIL import Image, ImageTk
import time



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
        self.button_1.config(text='StartLogging', command = lambda obj = self, key = 'StartLogging':obj.Button(key))
        self.button_1.pack(side='left')
        self.button_2 = ttk.Button(self.frame_1)
        self.button_2.config(text='SaveToXLS', command = lambda obj = self, key = 'SaveToXLS':obj.Button(key))
        self.button_2.pack(side='left')
        self.button_3 = ttk.Button(self.frame_1, command = lambda obj = self, key = 'Tar':obj.Button(key))
        self.button_3.config(text='Tar')
        self.button_3.pack(side='left')
        self.button_4 = ttk.Button(self.frame_1)
        self.button_4.config(text='ZERO', command = lambda obj = self, key = 'ZERO':obj.Button(key))
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
        imagebase = filter(lambda item: item[0]>time.time()-60, self.shared['json'].items())
        array = [[],[]]
        for number, val in imagebase:
            array[0].append(number - time.time())
            array[1].append(float(val[1]))
        label = self.shared['Values']['label']
        self.lock.release()
        if array[0] and array[1]:
            plot = pyplot.plot(array)
            plot.ylabel('Kg')
            plot.xlabel('time in s')
            image = plot.figure(figsize=(300,300))
            self.canvas_1.itemconfig(self.imageoncanvas, image=ImageTk.PhotoImage(image))
        self.text_1.delete('1.0',tk.END)
        self.text_1.insert('1.0',currentVal)
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
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.address = self.shared['address']
        self.lock.release()
        self.time = 0
        self.timeelapsed = 0
        if self.socket:
            try:
                self.socket.connect(self.address)
            except Exception as e:
                self.lock.acquire()
                self.shared['Values']['label'] = repr(e)
                self.lock.release()
            else:
                self.mainloop()
        else:
            self.lock.acquire()
            self.shared['Values']['label'] = 'Unable to connect with weight scale'
            self.lock.release()

    def mainloop(self):
        while True:
            self.elapsed = time.time() - self.time
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

    def logging(self):
        response = ''.encode()
        err=False
        while True:
            response += self.socket.recv(8)
            if '\r\n' in response.decode():
                break
            if not self.framecoherent(response) or len(response.decode())>30:
                err = True
                break
        response = response.decode()
        if self.timeelapsed > 10 and not err:
            self.lock.acquire()
            self.shared['json'].update([(time.time(),response[4:18])])
            json.dump(self.shared['json'],str(Path(__file__).parent.absolute())+'\\history.json')
            self.lock.release()
            self.timeelapsed = 0
            self.time = time.time()

    def Tar(self):
        self.socket.sendall('T\r\n'.encode())
        while True:
            response = ''.encode()
            err=False
            while True:
                response += self.socket.recv(8)
                if '\r\n' in response.decode():
                    break
                if not self.framecoherent(response.decode()) or len(response.decode())>30:
                    err = True
                    break
            if err: break
            response = response.decode()
            taring = 'T A' in response
            self.lock.acquire()
            self.shared['State']['WeightScaleBusy']=taring
            self.shared['Values']['Label']='Taring'
            self.lock.release()
            if not taring:
                break
        self.lock.acquire()
        self.shared['Buttons']['ZERO'] = False
        self.lock.release()

    def ZERO(self):
        self.socket.sendall('Z\r\n'.encode())
        while True:
            response = ''.encode()
            err=False
            while True:
                response += self.socket.recv(8)
                if '\r\n' in response:
                    break
                if not self.framecoherent(response.decode()) or len(response.decode())>30:
                    err = True
                    break
            if err: break
            response = response.decode()
            zeroing = 'T A' in response
            self.lock.acquire()
            self.shared['State']['WeightScaleBusy']=zeroing
            self.shared['Values']['Label']='Zeroing'
            self.lock.release()
            if not zeroing:
                break
        self.lock.acquire()
        self.shared['Buttons']['ZERO'] = False
        self.lock.release()

    def start(self, alreadyrunning):
        self.socket.sendall(str('CU'+str(int(alreadyrunning))+'\r\n').encode())
        response = ''
        while True:
            response += self.socket.recv(8)
            if '\r\n' in response:
                break
            if not self.framecoherent(response.decode()) or len(response.decode())>30:
                break
        response = response.decode()
        if 'CU'+str(int(alreadyrunning))+'A' in response:
            self.lock.acquire()
            self.shared['State']['Logging'] = not alreadyrunning
            self.lock.release()
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
        self.vaddress = ('',8080)
        try:
            self.vaddress=(self.configuration['Network']['IP'], self.configuration['Network']['port'])
        except:
            pass
        self.history = json.load(open(str(Path(__file__).parent.absolute())+'\\history.json'))
        self.shared = Manager()
        self.Lock = Lock()
        self.AppVariable = self.shared.dict({
            'json':self.shared.dict(self.history),
            'address':self.vaddress,
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
                'label':''
                
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
    freeze_support()
    Application = App()
    Application.run()