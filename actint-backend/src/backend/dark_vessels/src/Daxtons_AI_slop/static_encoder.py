import torch.nn as nn
import numpy as np



class StaticEncoder(nn.Module):
    """
    Encodes 7 static AIS features (imo, origincountry, vessel_type, length, width, draft, cargo, transceiverclass) → 3-dim latent space → reconstructs 6 features.
    Trained to minimise reconstruction error on normal ships only.
    """
    def __init__(self, input_dim=7, latent_dim=3):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32), nn.ReLU(),
            nn.Linear(32, 16),        nn.ReLU(),
            nn.Linear(16, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 16), nn.ReLU(),
            nn.Linear(16, 32),         nn.ReLU(),
            nn.Linear(32, input_dim),  nn.Sigmoid()
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z), z

    def reconstruction_error(self, x):
        recon, _ = self.forward(x)
        return ((recon - x) ** 2).mean(dim=1)
