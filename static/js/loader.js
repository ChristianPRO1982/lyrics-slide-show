document.addEventListener("DOMContentLoaded", () => {
    const loader = document.getElementById("loader");
    const content = document.getElementById("general");

    if (loader) loader.style.display = "none";
    if (content) content.style.display = "block";
});