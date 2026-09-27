import { Routes } from '@angular/router';
import { HomeComponent } from './pages/home/home.component';
import { SurpriseComponent } from './pages/surprise/surprise.component';
import { HaveIngredientsComponent } from './pages/have-ingredients/have-ingredients.component';
import { MyKitchenComponent } from './pages/my-kitchen/my-kitchen.component';
import { RecipeDetailComponent } from './pages/recipe-detail/recipe-detail.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'sorprendeme', component: SurpriseComponent },
  { path: 'con-lo-que-tengo', component: HaveIngredientsComponent },
  { path: 'mi-cocina', component: MyKitchenComponent },
  { path: 'receta/:id', component: RecipeDetailComponent },
  { path: '**', redirectTo: '' },
];
