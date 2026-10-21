document.addEventListener("DOMContentLoaded", () => {
  const carousel = document.querySelector("[data-featured-carousel]");
  document.querySelectorAll("[data-cover-image]").forEach((image) => {
    image.addEventListener("error", () => image.remove(), { once: true });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && window.location.hash.startsWith("#detalle-")) {
      window.location.hash = "#catalogo";
    }
  });

  if (!carousel) return;

  const slides = Array.from(carousel.querySelectorAll("[data-featured-slide]"));
  if (slides.length < 2) return;

  let activeIndex = 0;
  let timer = null;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function showSlide(index) {
    activeIndex = (index + slides.length) % slides.length;

    slides.forEach((slide, slideIndex) => {
      const isActive = slideIndex === activeIndex;
      slide.classList.toggle("is-active", isActive);
      slide.setAttribute("aria-hidden", isActive ? "false" : "true");

      slide.querySelectorAll("[data-carousel-slide]").forEach((dot) => {
        const dotIsActive = Number(dot.dataset.carouselSlide) === activeIndex;
        dot.classList.toggle("active", dotIsActive);
        dot.setAttribute("aria-pressed", dotIsActive ? "true" : "false");
      });
    });
  }

  function stopTimer() {
    if (timer) window.clearInterval(timer);
    timer = null;
  }

  function startTimer() {
    stopTimer();
    if (!reducedMotion) timer = window.setInterval(() => showSlide(activeIndex + 1), 6000);
  }

  carousel.addEventListener("click", (event) => {
    const next = event.target.closest("[data-carousel-next]");
    const previous = event.target.closest("[data-carousel-prev]");
    const dot = event.target.closest("[data-carousel-slide]");

    if (next) showSlide(activeIndex + 1);
    else if (previous) showSlide(activeIndex - 1);
    else if (dot) showSlide(Number(dot.dataset.carouselSlide));
    else return;

    startTimer();
  });

  carousel.addEventListener("mouseenter", stopTimer);
  carousel.addEventListener("mouseleave", startTimer);
  carousel.addEventListener("focusin", stopTimer);
  carousel.addEventListener("focusout", (event) => {
    if (!carousel.contains(event.relatedTarget)) startTimer();
  });

  startTimer();
});
