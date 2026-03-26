// TRANSLATION
const pageLanguage = document.documentElement.lang || 'fr';
if (pageLanguage.toLowerCase() == 'fr') {
    txt_fullscreen = 'APPUYEZ SUR F11 SUR CETTE ÉCRAN';
    txt_Description = "Description";
    txt_Add = "Ajouter";
    txt_Modify = "Modifier";
    txt_Delete = "Supprimer";
    err_qr_code = "Erreur lors de la génération du QR code";
    txt_qr_code_for_lyrics = "QR code pour les paroles des chants";
} else {
    txt_fullscreen = 'PRESS F11 ON THIS SCREEN';
    txt_Description = "Description";
    txt_Add = "Add";
    txt_Modify = "Modify";
    txt_Delete = "Delete";
    err_qr_code = "Error generating QR code";
    txt_qr_code_for_lyrics = "QR code for lyrics";
}

function toggleVisibility(id) {
    const element = document.getElementById(id);
    if (!element) return;

    // Set up transition only once
    if (!element.style.transition) {
        element.style.transition = "opacity 0.5s ease";
        element.style.opacity = element.style.display === "none" || element.style.display === "" ? "0" : "1";
    }

    if (element.style.display === "none" || element.style.opacity === "0") {
        element.style.display = "block";
        // Force reflow to enable transition
        void element.offsetWidth;
        element.style.opacity = "1";
    } else {
        element.style.opacity = "0";
        setTimeout(() => {
            if (element.style.opacity === "0") {
                element.style.display = "none";
            }
        }, 500);
    }
}

function toggleDivDisplay(id_div, id_a, txt_show, txt_hide) {
    const div = document.getElementById(id_div);
    const a = document.getElementById(id_a);
    if (!div || !a) return;

    // Ensure transition is set only once
    if (!div.style.transition) {
        div.style.transition = "max-height 0.5s ease, opacity 0.5s ease";
        div.style.overflow = "hidden";
        if (div.style.display === "" || div.style.display === "none") {
            div.style.maxHeight = "0";
            div.style.opacity = "0";
            div.style.display = "none";
        } else {
            div.style.maxHeight = div.scrollHeight + "px";
            div.style.opacity = "1";
        }
    }

    if (div.style.display === "none" || div.style.maxHeight === "0px" || div.style.opacity === "0") {
        div.style.display = "block";
        // Force reflow to enable transition
        void div.offsetWidth;
        div.style.maxHeight = div.scrollHeight + "px";
        div.style.opacity = "1";
        a.textContent = txt_hide;
    } else {
        div.style.maxHeight = "0";
        div.style.opacity = "0";
        a.textContent = txt_show;
        // After transition, hide the element
        setTimeout(() => {
            if (div.style.maxHeight === "0px") {
                div.style.display = "none";
            }
        }, 500);
    }
}

function addTextToInput(inputId, textToAdd, maxLength = 0) {
    var input = document.getElementById(inputId);
    if (!input) return;
    var current = input.value || '';
    if (maxLength <= 0) {
        maxLength = input.maxLength || 0;
    }
    var available = maxLength - current.length;
    if (available <= 0) {
        input.focus();
        return;
    }
    var toInsert = textToAdd.substring(0, available);
    input.value = current + toInsert;
    input.focus();
}

// mapping groupName -> inputName attendu côté Django
const inputNameMapping = {
  genres: 'genre_ids',
  bands: 'band_ids',
  artists: 'artist_ids',
};

function updateHiddenInputs(groupName) {
  const inputName = inputNameMapping[groupName];
  // Remove all previous hidden inputs in the target zone of this group
  const container = document.querySelector(`.transfer-container[data-group="${groupName}"]`);
  if (!container) return;

  container.querySelectorAll('li input[type="hidden"]').forEach(e => e.remove());

  // Add hidden inputs only to associated items (target zone)
  const targetZone = container.querySelector('[data-role="source"]');
  targetZone.querySelectorAll('li').forEach(item => {
    const id = item.dataset.id || item.dataset.genreId || item.dataset.themeId;
    if (!id) return;
    
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = inputName;
    input.value = id;
    item.appendChild(input);
  });
}

class TransferManager {
  constructor(groupName, onChangeCallback) {
    this.groupName = groupName;
    this.container = document.querySelector(`.transfer-container[data-group="${groupName}"]`);
    if (!this.container) return;

    this.sourceZone = this.container.querySelector('[data-role="source"]');
    this.targetZone = this.container.querySelector('[data-role="target"]');
    this.onChangeCallback = onChangeCallback;

    this.container.addEventListener('click', (event) => {
      const clickedItem = event.target.closest('li');
      if (!clickedItem) return;
      if (!this.container.contains(clickedItem)) return;

      this.transferItem(clickedItem);
      if (this.onChangeCallback) {
        this.onChangeCallback(this.groupName);
      }
    });
  }

  transferItem(item) {
    const currentZone = item.parentElement;
    const destinationZone = currentZone === this.sourceZone ? this.targetZone : this.sourceZone;
    destinationZone.appendChild(item);
  }

  static initAll(onChangeCallback) {
    const containers = document.querySelectorAll('.transfer-container');
    const groups = new Set();
    containers.forEach(container => {
      const group = container.getAttribute('data-group');
      if (group && !groups.has(group)) {
        groups.add(group);
        new TransferManager(group, onChangeCallback);
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  TransferManager.initAll(updateHiddenInputs);
});

function toggleVisibilityAfterSeconds(elementId, seconds) {
    setTimeout(() => {
        toggleVisibility(elementId);
    }, seconds * 1000);
}