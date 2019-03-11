#!/usr/bin/env python3
import sys
from time import sleep
from SX127x.LoRa import *
from SX127x.LoRaArgumentParser import LoRaArgumentParser
from SX127x.board_config import BOARD
import LoRaWAN
from LoRaWAN.MHDR import MHDR
import json,datetime

BOARD.setup()
parser = LoRaArgumentParser("LoRaWAN sender")

class LoRaWANsend(LoRa):
    def __init__(self, devaddr = [], nwkey = [], appkey = [], verbose = False):
        super(LoRaWANsend, self).__init__(verbose)
        self.devaddr = devaddr
        self.nwkey = nwkey
        self.appkey = appkey
        
    def on_tx_done(self):
        # 紀錄送出的時間
        global TX_TIMESTAMP
        TX_TIMESTAMP = datetime.datetime.now().timestamp()
        print("TxDone\n")
        # 切換到rx
        self.set_mode(MODE.STDBY)
        self.clear_irq_flags(TxDone=1)
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([0,0,0,0,0,0])
        self.set_invert_iq(1)
        self.reset_ptr_rx()
        sleep(1)
        self.set_mode(MODE.RXSINGLE)
        
    def on_rx_done(self):
        print("RxDone")
        self.clear_irq_flags(RxDone=1)
        
        # 讀取 payload
        payload = self.read_payload(nocheck=True)
        lorawan = LoRaWAN.new(nwskey, appskey)
        lorawan.read(payload)
        print("get mic: ",lorawan.get_mic())
        print("compute mic: ",lorawan.compute_mic())
        print("valid mic: ",lorawan.valid_mic())
        # 檢查mic
        if lorawan.valid_mic():
            print("ACK: ",lorawan.get_mac_payload().get_fhdr().get_fctrl()>>5&0x01)
            print("direction: ",lorawan.get_direction())
            print("devaddr: ",''.join(format(x, '02x') for x in lorawan.get_devaddr()))
            write_config()
        else:
            print("Wrong MIC")
        sys.exit(0)
    
    def send(self):
        global fCnt
        lorawan = LoRaWAN.new(nwskey, appskey)
        message = "HELLO WORLD!"
        # 資料打包,fCnt+1
        lorawan.create(MHDR.CONF_DATA_UP, {'devaddr': devaddr, 'fcnt': fCnt, 'data': list(map(ord, message)) })
        print("fCnt: ",fCnt)
        print("Send Message: ",message)
        fCnt = fCnt+1
        self.write_payload(lorawan.to_raw())
        self.set_mode(MODE.TX)
    
    def time_checking(self):
        global TX_TIMESTAMP
        diff = datetime.datetime.now().timestamp()-TX_TIMESTAMP
        # 檢查上次傳uplink的時間差
        if diff > 2 :
            print("TIMEOUT!!")
            write_config()
            sys.exit(0)
    
    def start(self):
        self.send()
        while True:
            self.time_checking()
            sleep(1)

def binary_array_to_hex(array):
    return ''.join(format(x, '02x') for x in array)

def write_config():
    global devaddr,nwskey,appskey,fCnt
    config = {'devaddr':binary_array_to_hex(devaddr),'nwskey':binary_array_to_hex(nwskey),'appskey':binary_array_to_hex(appskey),'fCnt':fCnt}
    data = json.dumps(config, sort_keys = True, indent = 4, separators=(',', ': '))
    fp = open("config.json","w")
    fp.write(data)
    fp.close()

def read_config():
    global devaddr,nwskey,appskey,fCnt
    config_file = open('config.json')
    parsed_json = json.load(config_file)
    devaddr = list(bytearray.fromhex(parsed_json['devaddr']))
    nwskey = list(bytearray.fromhex(parsed_json['nwskey']))
    appskey = list(bytearray.fromhex(parsed_json['appskey']))
    fCnt = parsed_json['fCnt']
    print("devaddr: ",parsed_json['devaddr'])
    print("nwskey : ",parsed_json['nwskey'])
    print("appskey: ",parsed_json['appskey'],"\n")

# Init
TX_TIMESTAMP = datetime.datetime.now().timestamp()
fCnt = 0
devaddr = []
nwskey = []
appskey = []
read_config()
lora = LoRaWANsend(False)

# Setup
lora.set_mode(MODE.SLEEP)
lora.set_dio_mapping([1,0,0,0,0,0])
lora.set_freq(923.4)
lora.set_pa_config(pa_select=1)
lora.set_spreading_factor(7)
lora.set_bw(BW.BW125)
lora.set_pa_config(max_power=0x0F, output_power=0x0E)
lora.set_sync_word(0x34)
lora.set_rx_crc(True)

#print(lora)
assert(lora.get_agc_auto_on() == 1)

try:
    print("Sending LoRaWAN message")
    lora.start()
except KeyboardInterrupt:
    sys.stdout.flush()
    print("\nKeyboardInterrupt")
finally:
    sys.stdout.flush()
    lora.set_mode(MODE.SLEEP)
    BOARD.teardown()
    write_config()
