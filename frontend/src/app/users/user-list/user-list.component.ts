import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { UserService, User } from '../services/user.service';

@Component({
  selector: 'app-user-list',
  standalone: true,
  imports: [CommonModule, MatTableModule, ZbButtonComponent],
  templateUrl: './user-list.component.html',
  styleUrl: './user-list.component.scss',
})
export class UserListComponent implements OnInit {
  users = signal<User[]>([]);
  loading = signal(true);

  displayedColumns = ['email', 'username', 'name', 'active', 'actions'];

  constructor(private userService: UserService) {}

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.userService.getUsers().subscribe({
      next: (users) => {
        this.users.set(users);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  toggleActive(user: User): void {
    this.userService.updateUser(user.id, { is_active: !user.is_active }).subscribe({
      next: () => this.loadUsers(),
    });
  }

  deleteUser(user: User): void {
    if (confirm(`¿Eliminar a ${user.email}?`)) {
      this.userService.deleteUser(user.id).subscribe({
        next: () => this.loadUsers(),
      });
    }
  }
}
