from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm, calculate_bearing
from datetime import datetime
import torch
from torch.utils.data import Dataset
import numpy as np
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence


class AISDataset(Dataset):
    def __init__(self, prepared_data):
        self.tracks = prepared_data['tracks'] #This is a list of lists of training data
        self.lengths = prepared_data['lengths'] #This is a list of track lengths.
        assert len(self.tracks) == len(self.lengths)

        # Convert numpy arrays to tensors
        self.tracks = [torch.tensor(track, dtype=torch.float32) for track in self.tracks]
        
        # Pad the end of the tracks with zeros so they are all the same length
        self.max_length = max(self.lengths)
        self.tracks = pad_sequence(self.tracks, batch_first=True, padding_value=0.0)
        
        
        # self.packed_tracks = pack_padded_sequence(self.tracks, self.lengths, batch_first=True, enforce_sorted=False)
        #packing things is usually for the batcher. Also remember to pack padded sequences for the batcher as well.


    def __len__(self):
        return len(self.tracks)

    def __getitem__(self, idx): #This will return the vessel type and a list of training data.
        training_data = self.tracks[idx]  # Already a tensor from pad_sequence
        track_length = torch.tensor(self.lengths[idx], dtype=torch.long)
        return track_length, training_data
        


def data_preparation(AIS_dynamic): # I need to get the static data 
    # Create mapping from vessel type strings to integers
    
    prepared_tracks = []
    track_lengths = []
    vessel_type_indices = []
    
    for num, track in enumerate(AIS_dynamic):
        n = len(track)
        if n > 700:
            print(f"skipping track {num + 1}/{len(AIS_dynamic)} with length {n} (too long)")
            continue
        track_lengths.append(n)
        features = np.zeros((n, 4))

        for i in range(n):

            if i == 0:
                lat_lon_distance = 0.0
                lat_lon_angle = 0.0
                msg_gap = 0.0
                training_time = 0.0
            else:
                if not (track[i]['basedatetime'] and track[i]['lat'] and track[i]['lon']): #skip over invalid data points
                    continue
                lat1 = track[i]['lat']
                lon1 = track[i]['lon']
                for j in range(i-1, -1, -1):
                    if track[j]['basedatetime'] and track[j]['lat'] and track[j]['lon']:
                        lat2 = track[j]['lat']
                        lon2 = track[j]['lon']
                        break
                lat_lon_distance = haversine_distance_nm(
                    lat1, lon1,
                    lat2, lon2
                )
                lat_lon_angle = calculate_bearing(
                    lat1, lon1,
                    lat2, lon2
                )
                msg_gap = (track[i]['basedatetime'] - track[i-1]['basedatetime']).total_seconds()
                training_time = np.log1p(msg_gap)
            features[i-1] = [lat_lon_distance, np.sin(lat_lon_angle), np.cos(lat_lon_angle), training_time]
        prepared_tracks.append(features)
        # Map vessel type string to integer
        print(f"prepared track {num + 1}/{len(AIS_dynamic)}")


    assert len(prepared_tracks) == len(track_lengths)
    prepared_data = {"vessel_type_numbers": vessel_type_indices, "tracks": prepared_tracks, "lengths": track_lengths}
    dataset = AISDataset(prepared_data)
    return dataset
#pad_tracks(prepared_tracks, FEATURE_NAMES)





class AISEncoder(nn.Module):

    def __init__(
        self,
        input_size=4,
        hidden_size=128,
        latent_size=64
    ):
        super().__init__()

        self.gru = nn.GRU(
            input_size=input_size,
            hidden_size=hidden_size,
            batch_first=True
        )

        self.projection = nn.Linear(
            hidden_size,
            latent_size
        )

    def forward(self, seq, lengths):

        if lengths is not None:
            packed = pack_padded_sequence(
                seq,
                lengths,
                batch_first=True,
                enforce_sorted=True
            )
            _, hidden = self.gru(packed)
        else:
            _, hidden = self.gru(seq)

        hidden = hidden[-1]
        latent = self.projection(hidden)

        return latent


class AISDecoder(nn.Module):
    def __init__(self, latent_size=64, hidden_size=128, output_size=4):
        super().__init__()

        self.gru = nn.GRU(
            input_size=hidden_size,
            hidden_size=hidden_size,
            batch_first=True
        )

        self.project = nn.Linear(hidden_size, output_size)

        self.expand = nn.Linear(latent_size, hidden_size)

    def forward(self, latent, seq_len):
        h = self.expand(latent)

        # repeat latent across time
        x = h.unsqueeze(1).repeat(1, seq_len, 1)

        out, _ = self.gru(x.contiguous())
        out = self.project(out)

        return out
    
    


class AISAutoencoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = AISEncoder()
        self.decoder = AISDecoder()

    def forward(self, x, lengths=None):
        latent = self.encoder(x, lengths)
        recon = self.decoder(latent, x.shape[1])
        return recon
    


from torch.utils.data import DataLoader
import torch
import torch.nn as nn


def train(model, dataset, epochs=200, batch_size=32, lr=1e-3):

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    for epoch in range(epochs):
        model.train()

        total_loss = 0.0

        for lengths, tracks in loader:

            tracks = tracks.to(device)
            lengths = lengths.to("cpu")  # IMPORTANT (PyTorch requirement)

            optimizer.zero_grad()

            # sort by length (IMPORTANT for cuDNN stability)
            lengths, idx = lengths.sort(descending=True)
            tracks = tracks[idx]

            recon = model(tracks, lengths)

            loss = criterion(recon, tracks)

            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        avg_loss = total_loss / len(loader)

        print(f"Epoch {epoch+1}/{epochs} Loss: {avg_loss:.4f}")






if __name__ == "__main__":
    from backend.mcp_servers.ais.helpers.vessel_query import get_all_mmsis, get_vessel_position_history_helper, query_static_data_helper
    from backend.dark_vessels.src.Daxtons_AI_slop.AIS_types import get_vessel_class
    mmsis = get_all_mmsis()
    vessel_numbers = []
    AIS_dynamic = []

    #get data prepared to go into the data preparer
    for mmsi in mmsis:
        #Only get AIS data where the vessel type is known
        static_info = query_static_data_helper({'mmsi': mmsi})[0]
        type = static_info['vesseltype']
        if type == None:
            continue
        type = get_vessel_class(type)
        if type == "Unknown":
            continue

        print(f"fetched static data for mmsi {mmsi}")
        print(f"fetching sorted dynamic data for mmsi {mmsi}")
        dynamic_data = get_vessel_position_history_helper(mmsi)
        dynamic_data.reverse()
        AIS_dynamic.append(dynamic_data)
        vessel_numbers.append(type)

    AIS_dataset = data_preparation(AIS_dynamic)
    
    model = AISAutoencoder()

    train(model, AIS_dataset, epochs=600)

