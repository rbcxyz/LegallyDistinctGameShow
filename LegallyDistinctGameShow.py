import pytchat
import threading
from collections import deque, defaultdict
from obswebsocket import obsws, requests
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import tkinter as tk
import yaml
import os
   
class LegallyDistinctGameShow:
    def __init__(self, obs, chat):
        self.active_cases = []
        self.obs = obs
        self.chat = chat
        self.fig = plt.figure()
        self.figure_path = config['selection_plot_filepath']

    def get_figure_path(self):
        return self.figure_path
    
    def start_plotting(self, active_cases):
        self.active_cases = active_cases
        plt.rcParams["figure.figsize"] = [10, 5]
        plt.rcParams["figure.autolayout"] = True

        counts = [0] * len(self.active_cases)
        self.bars = plt.bar(self.active_cases, counts)
        self.ani = FuncAnimation(self.fig, self._animate, interval=config['plot_refresh_rate'], frames=1)
        plt.xlabel("Case #")
        plt.ylabel("# of Votes")
        plt.title("Case Selection")
        plt.show()

    def stop_plotting(self):
        plt.close(self.fig)

    def calculate_chats_choices(self):
        messages = self.chat.get_new_messages()
        counts = defaultdict(lambda: 0)
        for msg in messages:
            for option in self.active_cases:
                if option in msg.message:
                    counts[option] += 1
        return counts

    def generate_bar_chart(self, counts):
        if len(counts.keys()) == 0:
            return
        for key in counts.keys():
            index = self.active_cases.index(key)
            self.bars[index].set_height(self.bars[index].get_height() + counts[key])
        plt.ylim([0, max(list(map(lambda x: x.get_height(), self.bars))) + 10])
        plt.savefig(self.figure_path)

    def _animate(self, frame):
        counts = self.calculate_chats_choices()
        self.generate_bar_chart(counts)

class OBS:
    def __init__(self):
        self.ws = obsws(config['obs_auth']['host'], config['obs_auth']['port'], config['obs_auth']['password'])
        self.ws.connect()

    def toggle_input(self, input_name, status):
        scene_name = config['obs_scene_settings']['scene_name']
        scene_item_list = self.ws.call(requests.GetSceneItemList(sceneName=scene_name)).getSceneItems()
        scene_item_id = next(item['sceneItemId'] for item in scene_item_list if item['sourceName'] == input_name)
        self.ws.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_item_id, sceneItemEnabled=status))

class Chat:
    def __init__(self):
        self.chat = pytchat.create(video_id=config['livestream_id'])
        self.new_messages = deque()
        self.chat_history = deque()
        self.lock = threading.Lock()
        self.running = True

    def scrape_chat(self):
        while self.running:
            if self.chat.is_alive():
                chat_data = self.chat.get()
                with self.lock:
                    for c in chat_data.items:
                        self.new_messages.append(c)
                        self.chat_history.append(c)
        print("Stream is over")

    def get_new_messages(self):
        with self.lock:
            return_messages = list(self.new_messages)
            self.new_messages = []
            return return_messages

    def format_message(self, msg):
        return f"{msg.datetime} [{msg.author.name}]- {msg.message}\n"

    def stop(self):
        self.running = False

class UI:

    def __init__(self):
        self.root = tk.Tk()
        self.threads = []
        self.video_id_entry = None
        self.active_cases = defaultdict(lambda: False)
        self.obs = OBS()
        self.chat = Chat()
        self.ldgs = LegallyDistinctGameShow(self.obs, self.chat)

    def start_plotting(self):
        chat_scraper_thread = threading.Thread(name="chat_scraper", target=self.chat.scrape_chat)
        chat_scraper_thread.start()
        self.threads.append(chat_scraper_thread)
        active_cases = []
        for key, value in self.active_cases.items():
            if value.get():
                active_cases.append(key)
        active_cases = ["a","b","c","d","e","i"]
        self.ldgs.start_plotting(active_cases)
    
    def stop_plotting(self):
        self.ldgs.stop_plotting()
        for thread in self.threads:
            thread.running = False

    def toggle_obs_case(self, case_name):
        self.obs.toggle_input(case_name, self.active_cases[case_name].get())

    def create_ui(self):
        self.root.title("Chat Plot Controller")
        self.root.geometry("800x600")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=10)
        self.root.grid_columnconfigure(0, weight=1)

        button_frame = tk.Frame(self.root)
        button_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        start_button = tk.Button(button_frame, text="Start", command=self.start_plotting)
        start_button.pack(side=tk.LEFT, padx=5, pady=5)

        stop_button = tk.Button(button_frame, text="Stop", command=self.stop_plotting)
        stop_button.pack(side=tk.LEFT, padx=5, pady=5)

        selector_frame = tk.Frame(self.root)
        selector_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        tk.Label(selector_frame, text="Active Cases:").grid(row=0, column=0, columnspan=6, padx=5, pady=5)

        checkbox_names = config['obs_scene_settings']['case_input_names']
        for i in range(len(checkbox_names)):
            var = tk.BooleanVar(value=True)
            checkbox_name = checkbox_names[i]
            checkbox = tk.Checkbutton(selector_frame, text=checkbox_name, variable=var, command=lambda i=checkbox_name: self.toggle_obs_case(i))
            row = (i // 6) + 1
            col = i % 6
            checkbox.grid(row=row, column=col, padx=5, pady=2, sticky="w")
            self.active_cases[checkbox_name] = var

        self.root.mainloop()

def main():
    global config
    config_file_path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__), 'config.yaml'))
    with open(config_file_path, "r") as f:
        config = yaml.safe_load(f)

    ui = UI()
    ui.create_ui()

if __name__ == "__main__":
    main()
