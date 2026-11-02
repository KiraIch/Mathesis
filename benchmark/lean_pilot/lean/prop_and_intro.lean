namespace MathesisPilot
theorem lean_prop_and_intro : ∀ (P Q : Prop), P → Q → P ∧ Q := by
  intro P
  intro Q
  intro hP
  intro hQ
  exact And.intro hP hQ
end MathesisPilot
