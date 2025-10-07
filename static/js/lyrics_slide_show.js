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

/**
DRAGGABLE DUAL-LIST
 * Initializes a draggable dual-list system.
 * @param {string} associatedListId - The ID of the list with associated items.
 * @param {string} availableListId - The ID of the list with available items.
 * @param {string} inputName - The name attribute to use for hidden input fields.
 */
/**
function initGenreDualList(associatedListId, availableListId, inputName = "genre_ids") {
    const associatedList = document.getElementById(associatedListId);
    const availableList = document.getElementById(availableListId);

    function moveItem(item, targetList) {
        targetList.appendChild(item);
        updateHiddenInputs();
    }

    function updateHiddenInputs() {
        // Clear all previous hidden inputs
        document.querySelectorAll(`#${associatedListId} .genre-item input[type="hidden"]`).forEach(e => e.remove());

        // Add input to each item in the associated list
        associatedList.querySelectorAll('.genre-item').forEach(item => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = inputName;
            input.value = item.dataset.genreId;
            item.appendChild(input);
        });
    }

    function setupList(list, targetList) {
        list.addEventListener('dragover', (e) => e.preventDefault());
        list.addEventListener('drop', (e) => {
            e.preventDefault();
            const genreId = e.dataTransfer.getData('text/plain');
            const item = document.querySelector(`.genre-item[data-genre-id="${genreId}"]`);
            if (item && item.parentNode !== list) {
                moveItem(item, list);
            }
        });

        list.querySelectorAll('.genre-item').forEach(item => {
            item.setAttribute('draggable', true);

            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', item.dataset.genreId);
            });

            item.addEventListener('dblclick', () => {
                moveItem(item, targetList);
            });
        });
    }

    setupList(associatedList, availableList);
    setupList(availableList, associatedList);
    updateHiddenInputs();  // Run once at init
}
*/

/**
 HTML example
 <h2>{% trans "Genres" %}</h2>
<div data-group="genres">
    <div style="display: flex; gap: 2em;">
        <div>
            <h4>{% trans "Associated genres" %}</h4>
            <ul id="genres-associated" class="genre-list" style="height: 10em; overflow: auto; border: 1px solid #ccc; padding: 8px;">
                
            </ul>
        </div>
        <div>
            <h4>{% trans "Available genres" %}</h4>
            <ul id="genres-available" class="genre-list" style="height: 10em; overflow: auto; border: 1px solid #ccc; padding: 8px;">
                <li class="genre-item" data-genre-id="1">exemple 1</li>
                <li class="genre-item" data-genre-id="2">exemple 2</li>
                <li class="genre-item" data-genre-id="3">exemple 3</li>
            </ul>
        </div>
    </div>
</div>

<h2>{% trans "Themes" %}</h2>
<div data-group="themes">
    <div style="display: flex; gap: 2em;">
        <div>
            <h4>{% trans "Associated themes" %}</h4>
            <ul id="themes-associated" class="genre-list" style="height: 10em; overflow: auto; border: 1px solid #ccc; padding: 8px;">
                
            </ul>
        </div>
        <div>
            <h4>{% trans "Available themes" %}</h4>
            <ul id="themes-available" class="genre-list" style="height: 10em; overflow: auto; border: 1px solid #ccc; padding: 8px;">
                <li class="genre-item" data-genre-id="4">exemple 4</li>
                <li class="genre-item" data-genre-id="5">exemple 5</li>
                <li class="genre-item" data-genre-id="6">exemple 6</li>
            </ul>
        </div>
    </div>
</div>

<script>
    document.addEventListener("DOMContentLoaded", function () {
        initGenreDualList("genres-associated", "genres-available", "genre_ids");
        initGenreDualList("themes-associated", "themes-available", "theme_ids");
    });
</script>
 */

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