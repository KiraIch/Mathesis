namespace MathesisPilot
theorem lean_list_map_map : ∀ {α β γ : Type} (f : α → β) (g : β → γ) (l : List α), List.map g (List.map f l) = List.map (g ∘ f) l := by
  intro α
  intro β
  intro γ
  intro f
  intro g
  intro l
  exact List.map_map
end MathesisPilot
