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
        self.fig = plt.figure(figsize=(7,5))
        self.figure_path = config['selection_plot_filepath']
        self.ani = None
        self.plt_show_called = False
    
    def get_figure_path(self):
        return self.figure_path
    
    def start_plotting(self, active_cases):
        if self.ani:
            return
        self.active_cases = active_cases
        counts = [0] * len(self.active_cases)
        self.bars = plt.bar(self.active_cases, counts)
        self.ani = FuncAnimation(self.fig, self._animate, interval=config['plot_refresh_rate'], frames=1)
        plt.xlabel("Case #")
        plt.ylabel("# of Votes")
        plt.title("Case Selection")
        plt.show()
        self.plt_show_called = True
    
    def stop_plotting(self):
        self.ani.event_source.stop()
        self.ani = None
        plt.close(self.fig)
        self.fig.clear()
        self.fig = plt.figure(figsize=(7,5))
        if os.path.exists(self.figure_path):
            os.remove(self.figure_path)

    def tally_votes(self):
        messages = self.chat.get_new_messages()
        counts = defaultdict(lambda: 0)
        for msg in messages:
            for option in self.active_cases:
                if option in msg.message:
                    counts[option] += 1
        return counts

    def update_votes_bar_chart(self, counts):
        if len(counts.keys()) == 0:
            return
        for key in counts.keys():
            index = self.active_cases.index(key)
            self.bars[index].set_height(self.bars[index].get_height() + counts[key])
        plt.ylim([0, max(list(map(lambda x: x.get_height(), self.bars))) + 10])
        plt.savefig(self.figure_path)

    def get_winning_vote(self):
        winning_case = ""
        max_value = 0
        for index, case in enumerate(self.active_cases):
            if self.bars[index].get_height() > max_value:
                max_value = self.bars[index].get_height()
                winning_case = case
        return winning_case

    def _animate(self, frame):
        counts = self.tally_votes()
        self.update_votes_bar_chart(counts)

class OBS:
    def __init__(self):
        self.ws = obsws(config['obs_auth']['host'], config['obs_auth']['port'], config['obs_auth']['password'])
        self.ws.connect()

    def disable_all_inputs(self, scene_name):
        scene_item_list = self.ws.call(requests.GetSceneItemList(sceneName=scene_name)).getSceneItems()
        for scene_item in scene_item_list:
            self.ws.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_item['sceneItemId'], sceneItemEnabled=False))

    def toggle_input(self, scene_name, input_name, status):
        scene_item_list = self.ws.call(requests.GetSceneItemList(sceneName=scene_name)).getSceneItems()
        scene_item_id = next(item['sceneItemId'] for item in scene_item_list if item['sourceName'] == input_name)
        self.ws.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_item_id, sceneItemEnabled=status))

    def switch_scene(self, next_scene):
        self.ws.call(requests.SetCurrentProgramScene(sceneName=next_scene))
        
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
        self.new_messages = deque()
        self.chat_history = deque()

    def get_new_messages(self):
        with self.lock:
            return_messages = list(self.new_messages)
            self.new_messages = []
            return return_messages

    def format_message(self, msg):
        return f"{msg.datetime} [{msg.author.name}]- {msg.message}\n"

    def stop(self):
        self.running = False

class App:

    def __init__(self):
        self.root = tk.Tk()
        self.threads = []
        self.video_id_entry = None
        self.active_cases = defaultdict(lambda: False)
        self.selected_case = ""
        self.obs = OBS()
        self.chat = Chat()
        self.ldgs = LegallyDistinctGameShow(self.obs, self.chat)
        self.plotting_active = False

    def start_plotting(self):
        if self.plotting_active:
            return
        self.chat.running = True
        chat_scraper_thread = threading.Thread(name="chat_scraper", target=self.chat.scrape_chat)
        chat_scraper_thread.start()
        self.threads.append(chat_scraper_thread)
        active_cases = []
        for key, value in self.active_cases.items():
            if value.get():
                active_cases.append(key)
        self.ldgs.start_plotting(active_cases)
        self.plotting_active = True

    def stop_plotting(self):
        self.plotting_active = False
        self.ldgs.stop_plotting()
        for thread in self.threads:
            self.chat.running = False
            thread.join()
    
    def switch_to_open_case_scene(self):
        self.selected_case = self.ldgs.get_winning_vote()
        if not self.selected_case:
            print("Voting is not yet underway. Press the 'Start' Button to open up voting for chat")
            return
        input_name = f'{self.selected_case}_staged'
        self.obs.disable_all_inputs(config['obs_scene_settings']['case_opening_scene_name'])
        self.obs.toggle_input(config['obs_scene_settings']['case_opening_scene_name'], config['obs_scene_settings']['case_opening_background'], True)
        self.obs.toggle_input(config['obs_scene_settings']['case_opening_scene_name'], input_name, True)
        self.obs.switch_scene(config['obs_scene_settings']['case_opening_scene_name'])

    def open_case(self):
        if not self.selected_case:
            print("No case has been staged. Use the 'Stage Case Opening' button first.")
            return
        self.obs.toggle_input(config['obs_scene_settings']['case_opening_scene_name'], f'{self.selected_case}_staged', False)
        self.obs.toggle_input(config['obs_scene_settings']['case_opening_scene_name'], f'{self.selected_case}_open', True)

    def switch_to_case_selection_scene(self):
        if self.selected_case:
            self.obs.toggle_input(config['obs_scene_settings']['case_selection_scene_name'], self.selected_case, False)
            self.active_cases[self.selected_case].set(False)
        self.obs.switch_scene(config['obs_scene_settings']['case_selection_scene_name'])

    def toggle_case(self, case_name):
        self.obs.toggle_input(config['obs_scene_settings']['case_selection_scene_name'], case_name, self.active_cases[case_name].get())

    def create_ui(self):
        self.root.title("Legally Distinct Game Show Controller")
        self.root.geometry("600x400")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=10)
        self.root.grid_columnconfigure(0, weight=1)

        button_frame = tk.Frame(self.root)
        button_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        button_padding = 15
        start_button = tk.Button(button_frame, text="Start", command=self.start_plotting)
        start_button.pack(side=tk.LEFT, padx=button_padding, pady=button_padding)

        stop_button = tk.Button(button_frame, text="Stop", command=self.stop_plotting)
        stop_button.pack(side=tk.LEFT, padx=button_padding, pady=button_padding)

        switch_to_case_opening_scene_button = tk.Button(button_frame, text="Stage Case Opening", command=self.switch_to_open_case_scene)
        switch_to_case_opening_scene_button.pack(side=tk.LEFT, padx=button_padding, pady=button_padding)

        open_case_button = tk.Button(button_frame, text="Open Staged Case", command=self.open_case)
        open_case_button.pack(side=tk.LEFT, padx=button_padding, pady=button_padding)

        switch_to_case_selection_scene_button = tk.Button(button_frame, text="Case Selection Screen", command=self.switch_to_case_selection_scene)
        switch_to_case_selection_scene_button.pack(side=tk.LEFT, padx=button_padding, pady=button_padding)

        selector_frame = tk.Frame(self.root)
        selector_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        tk.Label(selector_frame, text="Active Cases:").grid(row=0, column=0, columnspan=6, padx=5, pady=5)

        checkbox_names = config['obs_scene_settings']['case_input_names']
        for i in range(len(checkbox_names)):
            var = tk.BooleanVar(value=True)
            checkbox_name = checkbox_names[i]
            checkbox = tk.Checkbutton(selector_frame, text=checkbox_name, variable=var, command=lambda i=checkbox_name: self.toggle_case(i))
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

    app = App()
    app.create_ui()

if __name__ == "__main__":
    main()