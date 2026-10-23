import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconRegistry } from '@angular/material/icon';
import { MatToolbarModule } from '@angular/material/toolbar';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatButtonModule, MatToolbarModule],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  protected readonly titolo = 'Monitoraggio produzione — Pastificio';

  constructor() {
    // Le icone vengono dal font Material Symbols caricato in index.html.
    inject(MatIconRegistry).setDefaultFontSetClass('material-symbols-outlined');
  }
}
