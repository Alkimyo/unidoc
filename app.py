from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///unidoc.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # Default student
    department = db.Column(db.String(100))
    faculty = db.Column(db.String(100))
    student_id = db.Column(db.String(20), unique=True)  # Talaba ID, unikal bo'ladi
    group = db.Column(db.String(20))  # Yangi: talaba guruhi
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)  # Yangi: admin tomonidan faollashtirish
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(300))
    document_type = db.Column(db.String(50), nullable=False)  # thesis, assignment, report, etc.
    status = db.Column(db.String(20), default='draft')  # draft, submitted, approved, rejected, archived
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    department_head_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    dean_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    author = db.relationship('User', foreign_keys=[author_id], backref=db.backref('documents', lazy=True))
    supervisor = db.relationship('User', foreign_keys=[supervisor_id])
    department_head = db.relationship('User', foreign_keys=[department_head_id])
    dean = db.relationship('User', foreign_keys=[dean_id])

class DocumentApproval(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    approval_type = db.Column(db.String(20), nullable=False)  # supervisor, department_head, dean
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    document = db.relationship('Document', backref=db.backref('approvals', lazy=True))
    approver = db.relationship('User', backref=db.backref('approvals', lazy=True))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('notifications', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ROUTES
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Dashboard statistikalarini olish
    user_docs = Document.query.filter_by(author_id=current_user.id).count()
    pending_approvals = 0
    
    if current_user.role in ['teacher', 'department_head', 'dean']:
        pending_approvals = DocumentApproval.query.filter_by(
            approver_id=current_user.id, 
            status='pending'
        ).count()
    
    recent_docs = Document.query.filter_by(author_id=current_user.id).order_by(
        Document.created_at.desc()
    ).limit(5).all()
    
    return render_template('dashboard.html', 
                         user_docs=user_docs,
                         pending_approvals=pending_approvals,
                         recent_docs=recent_docs)

@app.route('/documents')
@login_required
def documents():
    user_docs = Document.query.filter_by(author_id=current_user.id).order_by(
        Document.created_at.desc()
    ).all()
    return render_template('documents.html', documents=user_docs)
# Helper funksiyalar
def get_my_students():
    """O'qituvchining talabalarini qaytaradi"""
    if current_user.role != 'teacher':
        return []
    # O'qituvchining kafedrasidagi talabalar
    return User.query.filter_by(
        role='student', 
        department=current_user.department
    ).all()

def get_department_users():
    """Kafedradagi barcha foydalanuvchilarni qaytaradi"""
    if current_user.role != 'department_head':
        return []
    return User.query.filter_by(department=current_user.department).all()

def get_faculty_users():
    """Fakultetdagi barcha foydalanuvchilarni qaytaradi"""
    if current_user.role != 'dean':
        return []
    return User.query.filter_by(faculty=current_user.faculty).all()

def get_all_users():
    """Barcha foydalanuvchilarni qaytaradi (faqat admin uchun)"""
    if current_user.role != 'admin':
        return []
    return User.query.all()

def get_available_supervisors():
    """Mavjud ilmiy rahbarlarni qaytaradi"""
    return User.query.filter_by(role='teacher').all()

def get_teachers():
    """Barcha o'qituvchilarni qaytaradi"""
    return User.query.filter_by(role='teacher').all()

def get_department_heads():
    """Barcha kafedra mudirlarini qaytaradi"""
    return User.query.filter_by(role='department_head').all()

def get_deans():
    """Barcha dekanlarni qaytaradi"""
    return User.query.filter_by(role='dean').all()

# Context processor - template'larda ishlatish uchun



@app.route('/create-document', methods=['GET', 'POST'])
@login_required
def create_document():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        document_type = request.form.get('document_type')
        
        # Hujjat turini tekshirish
        allowed_types = get_allowed_document_types(current_user.role)
        if document_type not in allowed_types and document_type != 'other':
            flash('Siz ushbu turdagi hujjat yarata olmaysiz', 'danger')
            return redirect(url_for('create_document'))
        
        # Muallifni aniqlash
        if current_user.role in ['admin', 'teacher', 'department_head', 'dean']:
            author_id = request.form.get('author_id', current_user.id)
        else:
            author_id = current_user.id
        
        # Muallif mavjudligini tekshirish
        author = User.query.get(author_id)
        if not author:
            flash('Tanlangan muallif topilmadi', 'danger')
            return redirect(url_for('create_document'))
        
        # Huquqni tekshirish
        if not can_create_document_for_user(current_user, author):
            flash('Siz ushbu foydalanuvchi uchun hujjat yarata olmaysiz', 'danger')
            return redirect(url_for('create_document'))
        
        # Yangi hujjat yaratish
        new_doc = Document(
            title=title,
            description=description,
            document_type=document_type,
            author_id=author_id,
            status='draft'
        )
        
        # Tasdiqlovchilarni qo'shish
        supervisor_id = request.form.get('supervisor_id')
        department_head_id = request.form.get('department_head_id')
        dean_id = request.form.get('dean_id')
        
        if supervisor_id:
            new_doc.supervisor_id = supervisor_id
        if department_head_id:
            new_doc.department_head_id = department_head_id
        if dean_id:
            new_doc.dean_id = dean_id
        
        db.session.add(new_doc)
        db.session.commit()
        
        flash('Hujjat muvaffaqiyatli yaratildi!', 'success')
        return redirect(url_for('documents'))
    
    return render_template('create_document.html')


# Huquq tekshirish funksiyasi
def can_create_document_for_user(current_user, target_user):
    """Joriy foydalanuvchi boshqa foydalanuvchi uchun hujjat yarata olishini tekshiradi"""
    if current_user.role == 'admin':
        return True
    elif current_user.role == 'dean':
        return target_user.faculty == current_user.faculty
    elif current_user.role == 'department_head':
        return target_user.department == current_user.department
    elif current_user.role == 'teacher':
        return (target_user.role == 'student' and 
                target_user.department == current_user.department)
    else:  # student
        return current_user.id == target_user.id
# Foydalanuvchi ma'lumotlari API (create_document uchun)
@app.route('/api/user/<int:user_id>/details')
@login_required
def get_user_details_for_document(user_id):
    user = User.query.get_or_404(user_id)
    
    # Huquq tekshirish
    if not can_create_document_for_user(current_user, user):
        return jsonify({'error': 'Ruxsat yo\'q'}), 403
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'department': user.department,
        'faculty': user.faculty,
        'student_id': user.student_id,
        'group': user.group
    })




@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        role = 'student'  # Faqat student roliga ruxsat
        department = request.form.get('department')
        faculty = request.form.get('faculty')
        student_id = request.form.get('student_id')
        group = request.form.get('group')
        
        # Validatsiya
        errors = []
        
        if User.query.filter_by(username=username).first():
            errors.append('Bu foydalanuvchi nomi band!')
        
        if User.query.filter_by(email=email).first():
            errors.append('Bu email manzili band!')
        
        if User.query.filter_by(student_id=student_id).first():
            errors.append('Bu Talaba ID band!')
        
        if password != confirm_password:
            errors.append('Parollar mos kelmadi!')
        
        if len(password) < 6:
            errors.append('Parol kamida 6 belgidan iborat bo\'lishi kerak!')
        
        if not student_id:
            errors.append('Talaba ID kiritilishi shart!')
        
        if not group:
            errors.append('Guruh kiritilishi shart!')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            # Yangi foydalanuvchi yaratish (faqat student rolida)
            new_user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                department=department,
                faculty=faculty,
                student_id=student_id,
                group=group,
                is_active=False  # Admin tasdiqlamaguncha faol emas
            )
            new_user.set_password(password)
            
            db.session.add(new_user)
            db.session.commit()
            
            # Adminlarga yangi ro'yxatdan o'tgan talaba haqida bildirishnoma yuborish
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                notification = Notification(
                    user_id=admin.id,
                    title="Yangi talaba ro'yxatdan o'tdi",
                    message=f"{first_name} {last_name} ({student_id}) tizimda ro'yxatdan o'tdi. Faollashtirish kerak."
                )
                db.session.add(notification)
            
            db.session.commit()
            
            flash('Ro\'yxatdan muvaffaqiyatli o\'tdingiz! Hisobingiz administrator tomonidan tekshirilgach faollashtiriladi.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

# Email tasdiqlash (keyinroq implement qilish mumkin)
@app.route('/verify-email/<token>')
def verify_email(token):
    # Email tasdiqlash logikasi
    flash('Email manzilingiz tasdiqlandi!', 'success')
    return redirect(url_for('login'))

# Parolni tiklash
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Parolni tiklash havolasini yuborish (keyinroq implement qilish)
            flash('Parolni tiklash havolasi email manzilingizga yuborildi.', 'info')
        else:
            flash('Bu email manzili bilan foydalanuvchi topilmadi.', 'danger')
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Parolni tiklash logikasi
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Parollar mos kelmadi!', 'danger')
        elif len(password) < 6:
            flash('Parol kamida 6 belgidan iborat bo\'lishi kerak!', 'danger')
        else:
            # Token ni tekshirish va parolni yangilash
            flash('Parolingiz muvaffaqiyatli yangilandi!', 'success')
            return redirect(url_for('login'))
    
    return render_template('reset_password.html')


@app.route('/approvals')
@login_required
def approvals():
    if current_user.role not in ['admin', 'dean', 'department_head', 'teacher']:
        flash('Sizda ushbu sahifaga kirish uchun ruxsat yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    # Foydalanuvchi roliga qarab tasdiqlanishi kerak bo'lgan hujjatlarni olish
    pending_docs = []
    
    if current_user.role == 'teacher':
        # O'qituvchi uchun - o'z talabalarining hujjatlari
        pending_docs = Document.query.filter(
            Document.supervisor_id == current_user.id,
            Document.status == 'submitted'
        ).all()
    elif current_user.role == 'department_head':
        # Kafedra mudiri uchun - kafedradagi barcha hujjatlar
        pending_docs = Document.query.filter(
            Document.department_head_id == current_user.id,
            Document.status == 'supervisor_approved'
        ).all()
    elif current_user.role == 'dean':
        # Dekan uchun - fakultetdagi barcha hujjatlar
        pending_docs = Document.query.filter(
            Document.dean_id == current_user.id,
            Document.status == 'department_approved'
        ).all()
    
    return render_template('approvals.html', pending_docs=pending_docs)

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Sizda admin paneliga kirish huquqi yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    users_count = User.query.count()
    documents_count = Document.query.count()
    pending_approvals_count = DocumentApproval.query.filter_by(status='pending').count()
    
    return render_template('admin_dashboard.html', 
                         users_count=users_count,
                         documents_count=documents_count,
                         pending_approvals_count=pending_approvals_count)


@app.route('/login', methods=['GET', "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        user = User.query.filter(
            (User.username == username)
        ).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Hisobingiz hali faollashtirilmagan. Iltimos, administrator bilan bog\'laning.', 'warning')
                return render_template('login.html')
            
            login_user(user)
            next_page = request.args.get('next')
            flash(f'Xush kelibsiz, {user.get_full_name()}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login yoki parol noto\'g\'ri', 'danger')
    
    return render_template('login.html')



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Siz tizimdan chiqdingiz', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

# API endpoints
@app.route('/api/notifications')
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    notifications_data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notifications]
    
    return jsonify({
        'count': len(notifications),
        'notifications': notifications_data
    })

@app.route('/api/document/<int:doc_id>/submit', methods=['POST'])
@login_required
def submit_document(doc_id):
    document = Document.query.get_or_404(doc_id)
    
    if document.author_id != current_user.id:
        return jsonify({'error': 'Siz faqat o\'z hujjatlaringizni yuborishingiz mumkin'}), 403
    
    document.status = 'submitted'
    db.session.commit()
    
    # Tasdiqlovchilarga bildirishnoma yuborish
    # Bu yerda notification yaratish logikasi
    
    return jsonify({'message': 'Hujjat muvaffaqiyatli yuborildi'})

@app.route('/api/document/<int:doc_id>/approve', methods=['POST'])
@login_required
def approve_document(doc_id):
    document = Document.query.get_or_404(doc_id)
    approval_type = request.json.get('approval_type')
    comments = request.json.get('comments', '')
    
    # Foydalanuvchining tasdiqlash huquqini tekshirish
    can_approve = False
    if current_user.role == 'teacher' and document.supervisor_id == current_user.id:
        can_approve = True
        next_status = 'supervisor_approved'
    elif current_user.role == 'department_head' and document.department_head_id == current_user.id:
        can_approve = True
        next_status = 'department_approved'
    elif current_user.role == 'dean' and document.dean_id == current_user.id:
        can_approve = True
        next_status = 'approved'  # Final approval
    
    if not can_approve:
        return jsonify({'error': 'Siz ushbu hujjatni tasdiqlash huquqiga ega emassiz'}), 403
    
    # Tasdiqlash yozuvini yaratish
    approval = DocumentApproval(
        document_id=doc_id,
        approver_id=current_user.id,
        approval_type=approval_type,
        status='approved',
        comments=comments
    )
    
    document.status = next_status
    db.session.add(approval)
    db.session.commit()
    
    return jsonify({'message': 'Hujjat muvaffaqiyatli tasdiqlandi'})

# My submissions route
@app.route('/my-submissions')
@login_required
def my_submissions():
    submissions = Document.query.filter_by(author_id=current_user.id).filter(
        Document.status.in_(['submitted', 'supervisor_approved', 'department_approved', 'approved', 'rejected'])
    ).order_by(Document.updated_at.desc()).all()
    
    return render_template('my_submissions.html', submissions=submissions)

# Document progress API
@app.route('/api/document/<int:doc_id>/progress')
@login_required
def document_progress(doc_id):
    document = Document.query.get_or_404(doc_id)
    
    # Foydalanuvchining hujjatni ko'rish huquqini tekshirish
    if document.author_id != current_user.id:
        return jsonify({'error': 'Siz faqat o\'z hujjatlaringizni ko\'ra olasiz'}), 403
    
    # Status klassini aniqlash
    status_classes = {
        'draft': 'warning',
        'submitted': 'info',
        'supervisor_approved': 'primary',
        'department_approved': 'primary',
        'approved': 'success',
        'rejected': 'danger'
    }
    
    # Status matnini aniqlash
    status_texts = {
        'draft': 'Qoralama',
        'submitted': 'Rahbar Tasdiqlashi Kutilmoqda',
        'supervisor_approved': 'Kafedra Tasdiqlashi Kutilmoqda',
        'department_approved': 'Dekan Tasdiqlashi Kutilmoqda',
        'approved': 'Tasdiqlangan',
        'rejected': 'Rad Etilgan'
    }
    
    # Jarayon bosqichlari
    steps = {
        'submitted': {
            'completed': document.status in ['submitted', 'supervisor_approved', 'department_approved', 'approved', 'rejected'],
            'active': document.status == 'submitted',
            'date': document.created_at.strftime('%d.%m.%Y %H:%M') if document.status in ['submitted', 'supervisor_approved', 'department_approved', 'approved', 'rejected'] else None
        },
        'supervisor': {
            'completed': document.status in ['supervisor_approved', 'department_approved', 'approved', 'rejected'],
            'active': document.status == 'supervisor_approved',
            'date': None
        },
        'department': {
            'completed': document.status in ['department_approved', 'approved', 'rejected'],
            'active': document.status == 'department_approved',
            'date': None
        },
        'dean': {
            'completed': document.status in ['approved', 'rejected'],
            'active': document.status == 'approved',
            'date': None
        }
    }
    
    # Tasdiqlash tarixi
    approvals_data = []
    for approval in document.approvals:
        approvals_data.append({
            'approver_name': approval.approver.get_full_name(),
            'approval_type': approval.approval_type.replace('_', ' ').title(),
            'status': 'Tasdiqlangan' if approval.status == 'approved' else 'Kutilyapti',
            'status_class': 'success' if approval.status == 'approved' else 'warning',
            'comments': approval.comments,
            'date': approval.created_at.strftime('%d.%m.%Y %H:%M')
        })
    
    # Taxminiy yakunlanish vaqti
    estimated_completion = None
    if document.status not in ['approved', 'rejected']:
        from datetime import timedelta
        est_date = document.updated_at + timedelta(days=7)
        estimated_completion = est_date.strftime('%d.%m.%Y')
    
    return jsonify({
        'id': document.id,
        'title': document.title,
        'type': document.document_type.replace('_', ' ').title(),
        'status': document.status,
        'status_class': status_classes.get(document.status, 'secondary'),
        'status_text': status_texts.get(document.status, document.status),
        'steps': steps,
        'approvals': approvals_data,
        'estimated_completion': estimated_completion
    })

# Hujjat turlarini roliga qarab aniqlash funksiyasi
def get_allowed_document_types(user_role):
    """Foydalanuvchi roliga qarab ruxsat etilgan hujjat turlarini qaytaradi"""
    if user_role == 'student':
        return {
            'diploma_project': 'Diplom loyihasi',
            'course_work': 'Kurs ishi', 
            'thesis': 'Magistrlik dissertatsiyasi',
            'scientific_article': 'Ilmiy maqola',
            'application': 'Ariza (stipendiya, akademik)',
            'other': 'Boshqa'
        }
    elif user_role == 'teacher':
        return {
            'diploma_project': 'Diplom loyihasi',
            'course_work': 'Kurs ishi',
            'thesis': 'Magistrlik dissertatsiyasi', 
            'scientific_article': 'Ilmiy maqola',
            'methodological_guide': 'Metodik qo\'llanma',
            'syllabus': 'O\'quv dasturi',
            'test_assignment': 'Test topshirig\'i',
            'report': 'Hisobot (ilmiy, o\'quv)',
            'application': 'Ariza',
            'other': 'Boshqa'
        }
    elif user_role == 'department_head':
        return {
            'department_report': 'Kafedra hisoboti',
            'work_plan': 'Ish rejasi',
            'protocol': 'Protokol',
            'order': 'Buyruq',
            'scientific_article': 'Ilmiy maqola',
            'methodological_guide': 'Metodik qo\'llanma',
            'report': 'Hisobot',
            'application': 'Ariza',
            'other': 'Boshqa'
        }
    elif user_role == 'dean':
        return {
            'faculty_report': 'Fakultet hisoboti',
            'order': 'Buyruq', 
            'protocol': 'Protokol',
            'work_plan': 'Ish rejasi',
            'academic_plan': 'O\'quv reja',
            'report': 'Hisobot',
            'application': 'Ariza',
            'other': 'Boshqa'
        }
    elif user_role == 'admin':
        return {
            'diploma_project': 'Diplom loyihasi',
            'course_work': 'Kurs ishi',
            'thesis': 'Magistrlik dissertatsiyasi',
            'scientific_article': 'Ilmiy maqola',
            'methodological_guide': 'Metodik qo\'llanma',
            'syllabus': 'O\'quv dasturi',
            'test_assignment': 'Test topshirig\'i',
            'department_report': 'Kafedra hisoboti',
            'faculty_report': 'Fakultet hisoboti',
            'work_plan': 'Ish rejasi',
            'academic_plan': 'O\'quv reja',
            'protocol': 'Protokol',
            'order': 'Buyruq',
            'report': 'Hisobot',
            'application': 'Ariza',
            'other': 'Boshqa'
        }
    else:
        return {}

# Context processor ga qo'shamiz
@app.context_processor
def utility_processor():
    return dict(
        get_my_students=get_my_students,
        get_department_users=get_department_users,
        get_faculty_users=get_faculty_users,
        get_all_users=get_all_users,
        get_available_supervisors=get_available_supervisors,
        get_teachers=get_teachers,
        get_department_heads=get_department_heads,
        get_deans=get_deans,
        get_allowed_document_types=get_allowed_document_types
    )



# Document resubmit API
@app.route('/api/document/<int:doc_id>/resubmit', methods=['POST'])
@login_required
def document_resubmit(doc_id):
    document = Document.query.get_or_404(doc_id)
    
    # Foydalanuvchining hujjatni qayta yuborish huquqini tekshirish
    if document.author_id != current_user.id:
        return jsonify({'error': 'Siz faqat o\'z hujjatlaringizni qayta yubora olasiz'}), 403
    
    if document.status != 'rejected':
        return jsonify({'error': 'Faqat rad etilgan hujjatlarni qayta yuborish mumkin'}), 400
    
    # Hujjatni qayta yuborish
    document.status = 'submitted'
    document.updated_at = datetime.utcnow()
    
    # Eski tasdiqlash yozuvlarini o'chirish
    DocumentApproval.query.filter_by(document_id=doc_id).delete()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Hujjat muvaffaqiyatli qayta yuborildi!'})

# Document view route
@app.route('/document/<int:doc_id>/view')
@login_required
def view_document(doc_id):
    document = Document.query.get_or_404(doc_id)
    
    # Foydalanuvchining hujjatni ko'rish huquqini tekshirish
    if document.author_id != current_user.id:
        flash('Siz faqat o\'z hujjatlaringizni ko\'ra olasiz', 'danger')
        return redirect(url_for('my_submissions'))
    
    return render_template('view_document.html', document=document)

@app.route('/supervise')
@login_required
def supervise():
    if current_user.role != 'teacher':
        flash('Sizda ushbu sahifaga kirish uchun ruxsat yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    # O'qituvchining talabalarining hujjatlari
    supervised_docs = Document.query.filter_by(supervisor_id=current_user.id).all()
    
    return render_template('supervise.html', supervised_docs=supervised_docs)

@app.route('/department-docs')
@login_required
def department_docs():
    if current_user.role != 'department_head':
        flash('Sizda ushbu sahifaga kirish uchun ruxsat yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    # Kafedradagi barcha hujjatlar
    department_docs = Document.query.filter_by(department=current_user.department).all()
    
    return render_template('department_docs.html', department_docs=department_docs)

@app.route('/faculty-docs')
@login_required
def faculty_docs():
    if current_user.role != 'dean':
        flash('Sizda ushbu sahifaga kirish uchun ruxsat yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    # Fakultetdagi barcha hujjatlar
    faculty_docs = Document.query.filter_by(faculty=current_user.faculty).all()
    
    return render_template('faculty_docs.html', faculty_docs=faculty_docs)

# Admin foydalanuvchi boshqaruvi
@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('Sizda admin paneliga kirish huquqi yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/add', methods=['POST'])
@login_required
def admin_add_user():
    if current_user.role != 'admin':
        return jsonify({'error': 'Ruxsat yo\'q'}), 403
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    role = request.form.get('role')
    department = request.form.get('department')
    faculty = request.form.get('faculty')
    student_id = request.form.get('student_id')
    group = request.form.get('group')
    
    # Validatsiya
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Bu foydalanuvchi nomi band!'})
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Bu email manzili band!'})
    
    if role == 'student' and User.query.filter_by(student_id=student_id).first():
        return jsonify({'error': 'Bu Talaba ID band!'})
    
    new_user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        department=department,
        faculty=faculty,
        student_id=student_id if role == 'student' else None,
        group=group if role == 'student' else None,
        is_active=True  # Admin tomonidan qo'shilgan foydalanuvchi darhol faol
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Foydalanuvchi muvaffaqiyatli qo\'shildi!'})

@app.route('/admin/users/<int:user_id>/activate', methods=['POST'])
@login_required
def admin_activate_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Ruxsat yo\'q'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    
    # Foydalanuvchiga bildirishnoma yuborish
    notification = Notification(
        user_id=user_id,
        title="Hisobingiz faollashtirildi",
        message="Sizning hisobingiz administrator tomonidan faollashtirildi. Endi tizimga kirishingiz mumkin."
    )
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Foydalanuvchi faollashtirildi!'})

@app.route('/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Ruxsat yo\'q'}), 403
    
    user = User.query.get_or_404(user_id)
    
    # O'zini o'chirishga yo'l qo'ymaslik
    if user.id == current_user.id:
        return jsonify({'error': 'O\'zingizni o\'chira olmaysiz!'})
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Foydalanuvchi o\'chirildi!'})


# Foydalanuvchi rolini yangilash
@app.route('/admin/users/<int:user_id>/update-role', methods=['POST'])
@login_required
def admin_update_user_role(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Ruxsat yo\'q'}), 403
    
    user = User.query.get_or_404(user_id)
    new_role = request.json.get('role')
    
    # O'zini o'zgartirishga yo'l qo'ymaslik
    if user.id == current_user.id:
        return jsonify({'error': 'O\'zingizning rol-ingizni o\'zgartira olmaysiz!'})
    
    # Rolni tekshirish
    valid_roles = ['student', 'teacher', 'department_head', 'dean', 'admin']
    if new_role not in valid_roles:
        return jsonify({'error': 'Noto\'g\'ri rol!'})
    
    # Rolni yangilash
    old_role = user.role
    user.role = new_role
    
    # Agar talaba rolidan boshqa rolga o'tsa, talaba ID va guruhni null qilish
    if old_role == 'student' and new_role != 'student':
        user.student_id = None
        user.group = None
    
    db.session.commit()
    
    # Log yozish
    print(f"Admin {current_user.username} foydalanuvchi {user.username} rolini {old_role} dan {new_role} ga o'zgartirdi")
    
    return jsonify({
        'success': True, 
        'message': f'Foydalanuvchi roli muvaffaqiyatli {new_role} ga o\'zgartirildi!',
        'new_role': new_role,
        'new_role_display': new_role.replace('_', ' ').title()
    })

# Foydalanuvchi ma'lumotlarini olish API
@app.route('/api/user/<int:user_id>/details')
@login_required
def get_user_details(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Ruxsat yo\'q'}), 403
    
    user = User.query.get_or_404(user_id)
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'department': user.department,
        'faculty': user.faculty,
        'student_id': user.student_id,
        'group': user.group,
        'is_active': user.is_active,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M'),
        'documents_count': len(user.documents)
    })




@app.route('/admin/documents')
@login_required
def admin_documents():
    if current_user.role != 'admin':
        flash('Sizda admin paneliga kirish huquqi yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    documents = Document.query.all()
    return render_template('admin_documents.html', documents=documents)

@app.route('/admin/logs')
@login_required
def admin_logs():
    if current_user.role != 'admin':
        flash('Sizda admin paneliga kirish huquqi yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('admin_logs.html')

@app.route('/admin/settings')
@login_required
def admin_settings():
    if current_user.role != 'admin':
        flash('Sizda admin paneliga kirish huquqi yo\'q', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('admin_settings.html')

# Statik sahifalar
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/help')
def help():
    return render_template('help.html')

# API endpoints for document details
@app.route('/api/document/<int:doc_id>/details')
@login_required
def document_details(doc_id):
    document = Document.query.get_or_404(doc_id)
    
    # Foydalanuvchining hujjatni ko'rish huquqini tekshirish
    if document.author_id != current_user.id and current_user.role not in ['admin', 'dean', 'department_head', 'teacher']:
        return jsonify({'error': 'Siz ushbu hujjatni ko\'ra olmaysiz'}), 403
    
    return jsonify({
        'id': document.id,
        'title': document.title,
        'author': document.author.get_full_name(),
        'type': document.document_type,
        'status': document.status,
        'description': document.description,
        'created_at': document.created_at.strftime('%Y-%m-%d')
    })














if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
